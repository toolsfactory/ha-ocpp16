"""Number-Plattform.

Dashboard-idiomatische Ergänzung zu den bestehenden ``ocpp.set_power_limit``/
``ocpp.clear_power_limit``-Services (Fähigkeit 3/4, kein eigener
Vertragsbestandteil, siehe INTEROP_CONTRACT.md).
"""

from custom_components.ocpp.runtime import OcppConfigEntry, OcppEntryData
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .power_limit import OcppPowerLimitNumber

# Jede Aktion löst einen Central-System-initiierten WebSocket-Aufruf an den
# Charge Point aus -- python-ocpps eigener _call_lock serialisiert diese pro
# Verbindung ohnehin, PARALLEL_UPDATES = 1 spiegelt das auf HA-Seite.
PARALLEL_UPDATES = 1

__all__ = ["OcppPowerLimitNumber", "async_setup_entry"]


async def async_setup_entry(
    hass: HomeAssistant, entry: OcppConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up number entities for a config entry."""
    manager = _NumberManager(entry.runtime_data, async_add_entities)
    entry.async_on_unload(manager.async_setup())


class _NumberManager:
    """Analog ``switch._SwitchManager``.

    Legt Number-Entities dynamisch je Connector an, sobald ein Charge Point
    erstmals bekannt wird. Reagiert auf ``OcppCoordinator``-Updates statt
    eigener Dispatcher-Signale.
    """

    def __init__(self, entry_data: OcppEntryData, async_add_entities: AddEntitiesCallback) -> None:
        self.entry_data = entry_data
        self.coordinator = entry_data.coordinator
        self.async_add_entities = async_add_entities
        self._known_connectors: set[tuple[str, int]] = set()

    def async_setup(self) -> CALLBACK_TYPE:
        """Start listening and sync already-known charge points. Returns the coordinator unsubscribe callable."""
        remove_listener = self.coordinator.async_add_listener(self._handle_coordinator_update)
        for snapshot in self.entry_data.app.query_service.get_charge_points():
            self._sync_connectors(snapshot.charge_point_id)
        return remove_listener

    @callback
    def _handle_coordinator_update(self) -> None:
        event = self.coordinator.data
        if event is None:
            return
        self._sync_connectors(event.charge_point_id, only_connector_id=event.connector_id)

    def _sync_connectors(self, charge_point_id: str, only_connector_id: int | None = None) -> None:
        query_service = self.entry_data.app.query_service
        connector_ids = (
            [only_connector_id]
            if only_connector_id is not None
            else [c.connector_id for c in query_service.get_connectors(charge_point_id)]
        )

        new_entities: list[OcppPowerLimitNumber] = []
        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008: kein charge-point-weiter v1-Scope.
            key = (charge_point_id, connector_id)
            if key in self._known_connectors:
                continue
            self._known_connectors.add(key)
            new_entities.append(OcppPowerLimitNumber(self.coordinator, self.entry_data, charge_point_id, connector_id))
        if new_entities:
            self.async_add_entities(new_entities)
