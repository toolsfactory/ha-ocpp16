"""Verdrahtet Transport, Domänenservices und die Konsole zu einem lauffähigen Kern.

WebSocket-Transport, Domänenservices, Query-/CommandService und optional die
interaktive Konsole (REQ-0032/REQ-0033) zu einem lauffähigen Standalone-Kern.
"""

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from custom_components.ocpp16.core.config import AppConfig
from custom_components.ocpp16.core.domain.authorization import AuthorizationProvider, StaticAuthorizationProvider
from custom_components.ocpp16.core.domain.commands import CommandService
from custom_components.ocpp16.core.domain.connector_state import ConnectorStateStore
from custom_components.ocpp16.core.domain.events import EventBus
from custom_components.ocpp16.core.domain.meter_values import MeterValueStore
from custom_components.ocpp16.core.domain.query import QueryServiceImpl
from custom_components.ocpp16.core.domain.registry import ChargePointRegistryStore
from custom_components.ocpp16.core.domain.transactions import TransactionManager
from custom_components.ocpp16.core.ocpp16.handlers import HandlerServices
from custom_components.ocpp16.core.transport import build_ssl_context, start_server

if TYPE_CHECKING:
    import ssl

    from websockets.asyncio.server import Server

logger = logging.getLogger(__name__)


class CentralSystemApp:
    """Composition root for the standalone core: wires config into runnable domain services."""

    def __init__(
        self,
        config: AppConfig,
        *,
        authorization: AuthorizationProvider | None = None,
        ssl_context: ssl.SSLContext | None = None,
    ) -> None:
        """Build the domain services and handler wiring from `config`.

        `authorization` lets a caller running inside an event loop (the HA layer) load the
        authorization file itself via an executor job and inject the result, instead of the
        blocking `Path.read_text()` in `StaticAuthorizationProvider.from_json_file()` running
        directly on the loop. The standalone CLI has no event loop yet at construction time
        (see ``__main__.py``), so it is safe to let this fall back to the synchronous load.

        `ssl_context` (Phase 5, direct `wss://`) mirrors `authorization` for the same reason:
        the HA layer builds it itself via an executor job, the standalone CLI falls back to
        the synchronous `build_ssl_context()` below.
        """
        self.config = config
        self.registry = ChargePointRegistryStore()
        self.connectors = ConnectorStateStore()
        self.transactions = TransactionManager()
        self.meter_values = MeterValueStore()
        self.events = EventBus()
        if authorization is not None:
            self.authorization = authorization
        elif config.authorization_file is not None:
            self.authorization = StaticAuthorizationProvider.from_json_file(config.authorization_file)
        else:
            self.authorization = StaticAuthorizationProvider.empty()
        if ssl_context is not None:
            self._ssl_context = ssl_context
        elif config.certificate_path is not None and config.private_key_path is not None:
            self._ssl_context = build_ssl_context(config.certificate_path, config.private_key_path)
        else:
            self._ssl_context = None
        self.query_service = QueryServiceImpl(
            registry=self.registry,
            connectors=self.connectors,
            transactions=self.transactions,
            meter_values=self.meter_values,
            events=self.events,
        )
        self.command_service = CommandService(registry=self.registry, transactions=self.transactions)
        self._handler_services = HandlerServices(
            registry=self.registry,
            connectors=self.connectors,
            transactions=self.transactions,
            meter_values=self.meter_values,
            authorization=self.authorization,
            events=self.events,
            heartbeat_interval_seconds=config.heartbeat_interval_seconds,
            heartbeat_grace_period_seconds=config.heartbeat_grace_period_seconds,
        )
        self._server: Server | None = None
        self._console_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Build the WebSocket server and bind the listen socket (ADR-0008).

        ``websockets.serve()`` kehrt nach dem Binden zurück, eingehende
        Verbindungen werden von der websockets-Bibliothek automatisch als
        eigene Tasks in der aktuell laufenden Eventloop eingeplant -- kein
        zusätzliches Task-Management durch den Aufrufer nötig. Muss aus
        einer bereits laufenden Eventloop heraus aufgerufen werden.
        """
        if self._server is not None:
            raise RuntimeError("CentralSystemApp.start() wurde ohne vorheriges stop() erneut aufgerufen.")
        self._server = await start_server(self.config, self._handler_services, ssl_context=self._ssl_context)

    async def stop(self) -> None:
        """Close the listen socket, open connections and the console task. Idempotent.

        Schließt den Listen-Socket und alle offenen Charge-Point-Verbindungen
        sowie einen ggf. laufenden Konsolen-Task (ADR-0008).
        """
        if self._console_task is not None:
            self._console_task.cancel()
            self._console_task = None

        if self._server is None:
            return
        server = self._server
        self._server = None
        server.close()
        await server.wait_closed()

    async def run(self) -> None:
        """Run the server until cancelled. Only for the standalone entry point (``__main__.py``).

        Baut auf ``start()``/``stop()`` auf statt Server-Aufbau und
        blockierendes Warten zu duplizieren (ADR-0008).
        """
        await self.start()
        assert self._server is not None

        if sys.stdin.isatty():
            # REQ-0032 AC4 / ADR-0002: Konsole nur bei echtem Terminal starten. Lazy
            # import, weil run() nur der Standalone-Einstiegspunkt aufruft -- die
            # HA-Integration lädt console.py nie.
            from custom_components.ocpp16.core.console import run_console  # noqa: PLC0415

            self._console_task = asyncio.create_task(run_console(self))
        else:
            logger.info(
                "Kein Terminal erkannt (sys.stdin.isatty() == False) — "
                "interaktive Konsole (REQ-0032/REQ-0033) bleibt deaktiviert."
            )

        try:
            if self._console_task is not None:
                await asyncio.gather(self._server.serve_forever(), self._console_task)
            else:
                await self._server.serve_forever()
        finally:
            await self.stop()
