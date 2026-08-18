"""Tests for `OccpMeasurandSensor`, the dynamic per-measurand sensor (REQ-0018)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


async def test_new_measurand_creates_a_sensor_with_mapped_unit_and_device_class(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A previously unseen measurand gets its own sensor, with the unit override and device class applied."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(
        entry_data.app,
        connector_id=1,
        measurand="Energy.Active.Import.Register",
        value="12345",
        unit="Wh",
    )
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{CHARGE_POINT_ID}_1_measurand_energy_active_import_register"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == "12345"
    assert state.attributes["unit_of_measurement"] == "Wh"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"


async def test_unmapped_measurand_still_gets_a_sensor(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A measurand outside `_MEASURAND_META` still creates a sensor, just without a device class."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, connector_id=1, measurand="RPM", value="1500", unit=None)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CHARGE_POINT_ID}_1_measurand_rpm")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == "1500"
    assert "device_class" not in state.attributes
