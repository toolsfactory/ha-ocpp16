"""Button-Plattform.

Dashboard-idiomatische Ergänzung zu den bestehenden ``ocpp16.reset``/
``ocpp16.unlock_connector``-Services (kein REQ-0035-Vertragsbestandteil).
"""

from custom_components.ocpp16.runtime import Ocpp16ConfigEntry, Ocpp16EntryData
from homeassistant.components.button import ButtonEntity
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .reset import Ocpp16ResetButton
from .unlock_connector import Ocpp16UnlockConnectorButton

# Jede Aktion löst einen Central-System-initiierten WebSocket-Aufruf an den
# Charge Point aus -- python-ocpps eigener _call_lock serialisiert diese pro
# Verbindung ohnehin, PARALLEL_UPDATES = 1 spiegelt das auf HA-Seite.
PARALLEL_UPDATES = 1

__all__ = ["Ocpp16ResetButton", "Ocpp16UnlockConnectorButton", "async_setup_entry"]


async def async_setup_entry(
    hass: HomeAssistant, entry: Ocpp16ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entities for a config entry."""
    manager = _ButtonManager(entry.runtime_data, async_add_entities)
    entry.async_on_unload(manager.async_setup())


class _ButtonManager:
    """Analog ``sensor._SensorManager``/``switch._SwitchManager``.

    Legt je Connector einen Unlock-Button und je Charge Point einen
    Reset-Button an, sobald diese erstmals bekannt werden. Reagiert auf
    ``Ocpp16Coordinator``-Updates statt eigener Dispatcher-Signale.
    """

    def __init__(self, entry_data: Ocpp16EntryData, async_add_entities: AddEntitiesCallback) -> None:
        self.entry_data = entry_data
        self.coordinator = entry_data.coordinator
        self.async_add_entities = async_add_entities
        self._known_connectors: set[tuple[str, int]] = set()
        self._known_charge_points: set[str] = set()

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

        new_entities: list[ButtonEntity] = []
        if charge_point_id not in self._known_charge_points:
            self._known_charge_points.add(charge_point_id)
            new_entities.append(Ocpp16ResetButton(self.coordinator, self.entry_data, charge_point_id))
        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008/ADR-0009: kein charge-point-weiter v1-Scope.
            key = (charge_point_id, connector_id)
            if key in self._known_connectors:
                continue
            self._known_connectors.add(key)
            new_entities.append(
                Ocpp16UnlockConnectorButton(self.coordinator, self.entry_data, charge_point_id, connector_id)
            )
        if new_entities:
            self.async_add_entities(new_entities)
