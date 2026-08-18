"""Push-Coordinator: treibt Entity-Updates aus ``QueryService.subscribe()`` statt Polling (ADR-0008).

``update_interval=None``: OCCPs eigene ADR-0008 lehnt Polling explizit ab
("kein Polling-Vorteil") -- der Kern kennt bereits einen Event-Bus
(``QueryService.subscribe``), der bei jeder relevanten OCPP-Nachricht feuert.

``coordinator.data`` hält bewusst nur das zuletzt empfangene
``StateChangeEvent``, keine materialisierte Kopie des gesamten Zustands:
``QueryService`` selbst ist bereits ein kostenloser, immer aktueller
In-Memory-Speicher (kein I/O, kein Staleness-Risiko) -- Entities lesen
weiterhin direkt daraus in ihren Property-Gettern, genau wie vor der
Koordinator-Einführung. Das Event dient ausschließlich dazu, dass ein
Listener (z. B. ein Central-System-initiierter Aufruf wie
``GetCompositeSchedule``) entscheiden kann, ob das Ereignis für seinen
eigenen Connector überhaupt relevant ist, bevor er unnötigen Traffic zum
Charge Point erzeugt.
"""

import logging

from custom_components.occp.const import DOMAIN
from custom_components.occp.core.app import CentralSystemApp
from custom_components.occp.core.domain.models import StateChangeEvent
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


class OccpCoordinator(DataUpdateCoordinator[StateChangeEvent | None]):
    """Benachrichtigt Entities über ``QueryService``-Ereignisse, ohne selbst zu pollen."""

    def __init__(self, hass: HomeAssistant, config_entry: ConfigEntry, app: CentralSystemApp) -> None:
        """Subscribe to `app.query_service` for the lifetime of this coordinator."""
        super().__init__(hass, _LOGGER, config_entry=config_entry, name=DOMAIN, update_interval=None)
        self.app = app
        self._unsubscribe_query_service = app.query_service.subscribe(self._on_state_change_event)

    def _on_state_change_event(self, event: StateChangeEvent) -> None:
        self.async_set_updated_data(event)

    def async_unsubscribe(self) -> None:
        """Stop listening to `app.query_service`."""
        self._unsubscribe_query_service()
