"""Binary sensor platform for occp."""

from typing import TYPE_CHECKING

from .filter import ENTITY_DESCRIPTIONS, OccpFilterSensor

# Read-only platform: the coordinator already serializes the fetch.
PARALLEL_UPDATES = 0

if TYPE_CHECKING:
    from custom_components.occp.data import OccpConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OccpConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the binary_sensor platform."""
    async_add_entities(
        OccpFilterSensor(entry.runtime_data.coordinator, description)
        for description in ENTITY_DESCRIPTIONS
    )
