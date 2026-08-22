"""WebSocket-Transport (REQ-0001, REQ-0027).

Subprotokoll-Aushandlung ``ocpp1.6``, Charge-Point-Identität aus dem
URL-Pfad, Verbindungs-Lebenszyklus (Connect/Disconnect-Logging REQ-0031,
Konfliktbehandlung bei doppelter Identität REQ-0001 AC4).

``websockets.serve(..., subprotocols=["ocpp1.6"])`` lehnt Verbindungen ohne
gemeinsames Subprotokoll bereits auf Bibliotheksebene ab (siehe
``websockets.server.ServerProtocol.select_subprotocol``): bietet ein Charge
Point ausschließlich z. B. ``ocpp2.0.1``/``ocpp2.1`` an (REQ-0027) oder gar
kein Subprotokoll, schlägt der Handshake fehl, ohne dass wir das selbst
prüfen müssten. Bietet er mehrere inkl. ``ocpp1.6`` an, wählt die Bibliothek
das erste in ``subprotocols`` gelistete gemeinsame Protokoll — mit nur einem
Eintrag ("ocpp1.6") ist das Ergebnis eindeutig.

Direktes TLS (``wss://``, Phase 5) ist optional: ``build_ssl_context`` baut einen
Server-``SSLContext`` aus einem Zertifikat/Schlüssel-Paar, ``start_server`` reicht ihn
unverändert an ``websockets.serve(..., ssl=...)`` weiter -- ohne Zertifikat bleibt
``ws://`` exakt wie zuvor.
"""

import asyncio
import logging
from pathlib import Path
import ssl

import websockets
from websockets.asyncio.server import Server, ServerConnection, serve
from websockets.typing import Subprotocol

from custom_components.ocpp16.core.config import AppConfig
from custom_components.ocpp16.core.domain.models import StateChangeEvent
from custom_components.ocpp16.core.logging_setup import get_charge_point_logger
from custom_components.ocpp16.core.ocpp16.handlers import ChargePointHandler, HandlerServices
from custom_components.ocpp16.core.ocpp16.watchdog import ConnectionWatchdog

logger = logging.getLogger(__name__)


def _extract_charge_point_id(connection: ServerConnection) -> str | None:
    path = connection.request.path if connection.request is not None else ""
    charge_point_id = path.strip("/")
    return charge_point_id or None


async def _run_connection(connection: ServerConnection, *, services: HandlerServices) -> None:
    charge_point_id = _extract_charge_point_id(connection)
    if not charge_point_id:
        logger.warning(
            "WebSocket-Verbindung ohne Charge-Point-Identität im Pfad abgelehnt (%s)",
            connection.remote_address,
        )
        await connection.close(code=1008, reason="missing charge point identity")
        return

    cp_logger = get_charge_point_logger(charge_point_id)
    handler = ChargePointHandler(charge_point_id, connection, services=services, cp_logger=cp_logger)

    previous = services.registry.register_connection(charge_point_id, handler)
    if previous is not None:
        cp_logger.info(
            "Neue Verbindung für bereits verbundene Identität eingetroffen — "
            "schließe bestehende Verbindung aktiv (REQ-0001 AC4)"
        )
        await previous.close_connection(reason="replaced by new connection")

    cp_logger.info("Charge Point verbunden (%s)", connection.remote_address)
    services.events.publish(StateChangeEvent(charge_point_id, None, None))

    watchdog = ConnectionWatchdog(
        timeout_seconds=services.heartbeat_timeout_seconds,
        on_timeout=lambda: _on_heartbeat_timeout(handler, cp_logger),
    )
    handler.attach_watchdog_notifier(watchdog.notify_activity)
    watchdog_task = asyncio.create_task(watchdog.run())

    try:
        await handler.start()
    except websockets.ConnectionClosed as exc:
        cp_logger.warning("Verbindung unerwartet getrennt: %s", exc)
    finally:
        watchdog_task.cancel()
        services.registry.mark_disconnected(charge_point_id, handler)
        cp_logger.info("Charge Point getrennt")
        services.events.publish(StateChangeEvent(charge_point_id, None, None))


async def _on_heartbeat_timeout(handler: ChargePointHandler, cp_logger: logging.LoggerAdapter) -> None:
    cp_logger.warning("Kein Lebenszeichen innerhalb des Toleranzfensters (REQ-0003) — trenne Verbindung")
    await handler.close_connection(reason="heartbeat timeout")


def build_ssl_context(certificate_path: Path, private_key_path: Path) -> ssl.SSLContext:
    """Build a server-side TLS context for direct `wss://` support (Phase 5, no reverse proxy needed).

    Läuft synchron (Datei-I/O + Zertifikats-Parsing) -- Aufrufer, die bereits in einer
    laufenden Eventloop stehen (HA-Layer, Config-Flow-Validator), müssen
    ``hass.async_add_executor_job`` nutzen. Wirft ``OSError`` (nicht lesbar/vorhanden)
    oder ``ssl.SSLError`` (kein gültiges PEM-Zertifikat/Schlüssel-Paar bzw. Mismatch).
    """
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=certificate_path, keyfile=private_key_path)
    return context


async def start_server(
    config: AppConfig, services: HandlerServices, *, ssl_context: ssl.SSLContext | None = None
) -> Server:
    """Start the OCPP 1.6 WebSocket server and return the bound `Server`.

    `ssl_context` enables direct `wss://` (Phase 5); `None` keeps the unchanged `ws://`
    default.
    """

    async def handler(connection: ServerConnection) -> None:
        await _run_connection(connection, services=services)

    server = await serve(
        handler,
        config.host,
        config.port,
        subprotocols=[Subprotocol("ocpp1.6")],
        ssl=ssl_context,
    )
    scheme = "wss" if ssl_context is not None else "ws"
    logger.info("OCPP-1.6-WebSocket-Server läuft auf %s://%s:%s", scheme, config.host, config.port)
    return server
