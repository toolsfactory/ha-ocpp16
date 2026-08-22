"""Button-Plattform.

Dashboard-idiomatische Ergänzung zu den bestehenden ``ocpp16.reset``/
``ocpp16.unlock_connector``-Services (kein REQ-0035-Vertragsbestandteil).
"""

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.entity_utils.dynamic_platform import DynamicPlatformManager
from custom_components.ocpp16.runtime import Ocpp16ConfigEntry, Ocpp16EntryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .reset import Ocpp16ResetButton
from .unlock_connector import Ocpp16UnlockConnectorButton

# Jede Aktion löst einen Central-System-initiierten WebSocket-Aufruf an den
# Charge Point aus -- python-ocpps eigener _call_lock serialisiert diese pro
# Verbindung ohnehin, PARALLEL_UPDATES = 1 spiegelt das auf HA-Seite.
PARALLEL_UPDATES = 1

__all__ = ["Ocpp16ResetButton", "Ocpp16UnlockConnectorButton", "async_setup_entry"]


def _connector_entities(
    coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
) -> list[Entity]:
    return [Ocpp16UnlockConnectorButton(coordinator, entry_data, charge_point_id, connector_id)]


def _charge_point_entities(
    coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str
) -> list[Entity]:
    return [Ocpp16ResetButton(coordinator, entry_data, charge_point_id)]


async def async_setup_entry(
    hass: HomeAssistant, entry: Ocpp16ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up button entities for a config entry."""
    manager = DynamicPlatformManager(
        entry.runtime_data,
        async_add_entities,
        connector_entity_factory=_connector_entities,
        charge_point_entity_factory=_charge_point_entities,
    )
    entry.async_on_unload(manager.async_setup())
