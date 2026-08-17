"""Verdrahtet WebSocket-Transport, Domänenservices, Query-/CommandService und
optional die interaktive Konsole (REQ-0032/REQ-0033) zu einem lauffähigen
Standalone-Kern.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from typing import TYPE_CHECKING

from custom_components.occp.core.config import AppConfig
from custom_components.occp.core.domain.authorization import StaticAuthorizationProvider
from custom_components.occp.core.domain.commands import CommandService
from custom_components.occp.core.domain.connector_state import ConnectorStateStore
from custom_components.occp.core.domain.events import EventBus
from custom_components.occp.core.domain.meter_values import MeterValueStore
from custom_components.occp.core.domain.query import QueryServiceImpl
from custom_components.occp.core.domain.registry import ChargePointRegistryStore
from custom_components.occp.core.domain.transactions import TransactionManager
from custom_components.occp.core.ocpp16.handlers import HandlerServices
from custom_components.occp.core.transport import start_server

if TYPE_CHECKING:
    from websockets.asyncio.server import Server

logger = logging.getLogger(__name__)


class CentralSystemApp:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.registry = ChargePointRegistryStore()
        self.connectors = ConnectorStateStore()
        self.transactions = TransactionManager()
        self.meter_values = MeterValueStore()
        self.events = EventBus()
        self.authorization = (
            StaticAuthorizationProvider.from_json_file(config.authorization_file)
            if config.authorization_file is not None
            else StaticAuthorizationProvider.empty()
        )
        self.query_service = QueryServiceImpl(
            registry=self.registry,
            connectors=self.connectors,
            transactions=self.transactions,
            meter_values=self.meter_values,
            events=self.events,
        )
        self.command_service = CommandService(
            registry=self.registry, transactions=self.transactions
        )
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
        self._server: "Server | None" = None
        self._console_task: asyncio.Task | None = None

    async def start(self) -> None:
        """Baut den WebSocket-Server auf und bindet den Listen-Socket
        (ADR-0008). ``websockets.serve()`` kehrt nach dem Binden zurück,
        eingehende Verbindungen werden von der websockets-Bibliothek
        automatisch als eigene Tasks in der aktuell laufenden Eventloop
        eingeplant — kein zusätzliches Task-Management durch den Aufrufer
        nötig. Muss aus einer bereits laufenden Eventloop heraus aufgerufen
        werden."""
        if self._server is not None:
            raise RuntimeError(
                "CentralSystemApp.start() wurde ohne vorheriges stop() erneut "
                "aufgerufen."
            )
        self._server = await start_server(self.config, self._handler_services)

    async def stop(self) -> None:
        """Schließt den Listen-Socket und alle offenen Charge-Point-
        Verbindungen sowie einen ggf. laufenden Konsolen-Task (ADR-0008).
        Idempotent."""
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
        """NUR für den Standalone-Einstiegspunkt (``__main__.py``): baut auf
        ``start()``/``stop()`` auf statt Server-Aufbau und blockierendes
        Warten zu duplizieren (ADR-0008)."""
        await self.start()
        assert self._server is not None

        if sys.stdin.isatty():
            # REQ-0032 AC4 / ADR-0002: Konsole nur bei echtem Terminal starten.
            from custom_components.occp.core.console import run_console

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
