"""Change-Notification ohne Polling-Zwang (REQ-0011 AC2).

Listener-Aufrufe erfolgen synchron aus dem Event Loop des Kerns heraus und
dürfen laut interfaces.md nicht blockieren; der Aufrufer muss langlaufende
Reaktionen selbst entkoppeln (z. B. später ``hass.async_create_task``).
"""

from collections.abc import Callable
import contextlib
import logging

from custom_components.occp.core.domain.models import StateChangeEvent, StateChangeListener

logger = logging.getLogger(__name__)


class EventBus:
    """In-process publish/subscribe bus for domain state-change events."""

    def __init__(self) -> None:
        """Initialize an empty listener registry."""
        self._listeners: list[StateChangeListener] = []

    def publish(self, event: StateChangeEvent) -> None:
        """Call every subscribed listener with `event`, isolating listener failures."""
        for listener in tuple(self._listeners):
            try:
                listener(event)
            except Exception:
                # den Kern/andere Listener nicht stören.
                logger.exception("Fehler in StateChangeListener für Ereignis %s", event)

    def subscribe(self, listener: StateChangeListener) -> Callable[[], None]:
        """Register `listener` and return a callable that unsubscribes it."""
        self._listeners.append(listener)

        def unsubscribe() -> None:
            with contextlib.suppress(ValueError):
                self._listeners.remove(listener)

        return unsubscribe
