"""Tests for `OccpCurrentPowerSensor` (Fähigkeit 1, REQ-0035 AC1)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN, MEASURAND_POWER_ACTIVE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


async def test_unavailable_until_a_power_sample_is_reported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """REQ-0035 AC1: unavailable until a matching measurand has been reported, not `0`."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CHARGE_POINT_ID}_1_current_power_w")
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "unavailable"

    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1500", unit="W", connector_id=1)
    publish_state_change(entry_data.app, connector_id=1)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1500.0"
    assert state.attributes["unit_of_measurement"] == "W"
