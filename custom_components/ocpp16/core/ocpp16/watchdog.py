"""Heartbeat-/Health-Monitoring (REQ-0003).

Jede eingehende Nachricht gilt als Lebenszeichen (REQ-0003 AC3), nicht nur
``Heartbeat`` selbst — der Aufrufer ruft ``notify_activity()`` bei jeder über
``route_message`` eingehenden Nachricht auf. Toleranz = 2x vereinbartes
Intervall + feste Grace-Period (Entscheidung REQ-0003).
"""

import asyncio
from collections.abc import Awaitable, Callable


class ConnectionWatchdog:
    """Ruft `on_timeout` auf, wenn keine Aktivität innerhalb des Toleranzfensters eintrifft."""

    def __init__(self, *, timeout_seconds: float, on_timeout: Callable[[], Awaitable[None]]) -> None:
        """Initialize the watchdog with its timeout and timeout callback."""
        self._timeout_seconds = timeout_seconds
        self._on_timeout = on_timeout
        self._activity = asyncio.Event()
        self._activity.set()

    def notify_activity(self) -> None:
        """Reset the tolerance window; call on every received message."""
        self._activity.set()

    async def run(self) -> None:
        """Run until the tolerance window elapses without activity, then call `on_timeout` once.

        Bei ``asyncio.CancelledError`` (reguläre Verbindungsbeendigung) wird
        sauber beendet, ohne ``on_timeout`` aufzurufen.
        """
        while True:
            self._activity.clear()
            try:
                await asyncio.wait_for(self._activity.wait(), timeout=self._timeout_seconds)
            except TimeoutError:
                await self._on_timeout()
                return
