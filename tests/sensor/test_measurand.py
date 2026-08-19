"""Tests for `OccpMeasurandSensor`, the dynamic per-measurand sensor (REQ-0018)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from custom_components.occp.entity_utils.device import connector_identifier
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

    unique_id = (
        f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_measurand_energy_active_import_register"
    )
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == "12345"
    assert state.attributes["unit_of_measurement"] == "Wh"
    assert state.attributes["device_class"] == "energy"
    assert state.attributes["state_class"] == "total_increasing"


async def test_multi_phase_samples_of_the_same_measurand_do_not_overwrite_each_other(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """L1/L2/L3 readings of the same measurand are stored separately, not last-write-wins."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, connector_id=1, measurand="Current.Import", value="6", unit="A", phase="L1")
    record_meter_sample(entry_data.app, connector_id=1, measurand="Current.Import", value="7", unit="A", phase="L2")
    record_meter_sample(entry_data.app, connector_id=1, measurand="Current.Import", value="8", unit="A", phase="L3")
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    registry = er.async_get(hass)
    connector_id = connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)
    for phase, expected_value in (("l1", "6"), ("l2", "7"), ("l3", "8")):
        entity_id = registry.async_get_entity_id("sensor", DOMAIN, f"{connector_id}_measurand_current_import_{phase}")
        assert entity_id is not None, f"no entity for phase {phase}"
        assert hass.states.get(entity_id).state == expected_value


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

    unique_id = f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_measurand_rpm"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state.state == "1500"
    assert "device_class" not in state.attributes
