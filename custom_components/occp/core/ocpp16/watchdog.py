"""Heartbeat-/Health-Monitoring (REQ-0003).

Jede eingehende Nachricht gilt als Lebenszeichen (REQ-0003 AC3), nicht nur
``Heartbeat`` selbst — der Aufrufer ruft ``notify_activity()`` bei jeder über
``route_message`` eingehenden Nachricht auf. Toleranz = 2x vereinbartes
Intervall + feste Grace-Period (Entscheidung REQ-0003).
"""

from __future__ import annotations

import asyncio
from typing import Awaitable, Callable


class ConnectionWatchdog:
    def __init__(self, *, timeout_seconds: float, on_timeout: Callable[[], Awaitable[None]]) -> None:
        self._timeout_seconds = timeout_seconds
        self._on_timeout = on_timeout
        self._activity = asyncio.Event()
        self._activity.set()

    def notify_activity(self) -> None:
        self._activity.set()

    async def run(self) -> None:
        """Läuft, bis das Toleranzfenster ohne Lebenszeichen abläuft, und
        ruft dann ``on_timeout`` genau einmal auf. Bei ``asyncio.CancelledError``
        (reguläre Verbindungsbeendigung) wird sauber beendet, ohne
        ``on_timeout`` aufzurufen.
        """
        while True:
            self._activity.clear()
            try:
                await asyncio.wait_for(
                    self._activity.wait(), timeout=self._timeout_seconds
                )
            except asyncio.TimeoutError:
                await self._on_timeout()
                return
