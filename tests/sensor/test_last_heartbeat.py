"""Tests for `Ocpp16LastHeartbeatSensor`."""

from collections.abc import Callable
from datetime import UTC, datetime

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.entity_utils.device import charge_point_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{charge_point_identifier(entry_id, CHARGE_POINT_ID)}_last_heartbeat"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_unknown_until_a_heartbeat_is_recorded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`unknown` (not `unavailable` -- the charge point is online) until the first heartbeat arrives."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "unknown"


async def test_updates_when_a_heartbeat_is_recorded(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`mark_heartbeat` followed by a `StateChangeEvent` updates the sensor's value."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    heartbeat_at = datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
    entry_data.app.registry.mark_heartbeat(CHARGE_POINT_ID, heartbeat_at)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == heartbeat_at.isoformat()
