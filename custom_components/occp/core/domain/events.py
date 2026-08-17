"""Change-Notification ohne Polling-Zwang (REQ-0011 AC2).

Listener-Aufrufe erfolgen synchron aus dem Event Loop des Kerns heraus und
dürfen laut interfaces.md nicht blockieren; der Aufrufer muss langlaufende
Reaktionen selbst entkoppeln (z. B. später ``hass.async_create_task``).
"""

from __future__ import annotations

import logging
from typing import Callable

from custom_components.occp.core.domain.models import StateChangeEvent, StateChangeListener

logger = logging.getLogger(__name__)


class EventBus:
    def __init__(self) -> None:
        self._listeners: list[StateChangeListener] = []

    def publish(self, event: StateChangeEvent) -> None:
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:  # noqa: BLE001 - ein fehlerhafter Listener darf
                # den Kern/andere Listener nicht stören.
                logger.exception("Fehler in StateChangeListener für Ereignis %s", event)

    def subscribe(self, listener: StateChangeListener) -> Callable[[], None]:
        self._listeners.append(listener)

        def unsubscribe() -> None:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

        return unsubscribe
