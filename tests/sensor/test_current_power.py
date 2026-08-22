"""Tests for `Ocpp16CurrentPowerSensor` (Fähigkeit 1, REQ-0035 AC1)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp16.const import DOMAIN, MEASURAND_POWER_ACTIVE_IMPORT
from custom_components.ocpp16.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


async def test_unknown_until_a_power_sample_is_reported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """`unknown` (not `0`, and not `unavailable` -- the charge point is online) until a sample arrives."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "unknown"

    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1500", unit="W", connector_id=1)
    publish_state_change(entry_data.app, connector_id=1)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state.state == "1500.0"
    assert state.attributes["unit_of_measurement"] == "W"


async def test_kw_value_is_converted_to_watts(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A `kW`-unit sample is scaled to watts, not treated as if it were already W."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="7.4", unit="kW", connector_id=1)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert hass.states.get(entity_id).state == "7400.0"


async def test_missing_unit_is_treated_as_watts(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A sample without a unit is treated as watts, OCPP 1.6's implicit default for this measurand."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="500", unit=None, connector_id=1)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert hass.states.get(entity_id).state == "500.0"


async def test_non_numeric_value_does_not_crash(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A non-numeric sample value doesn't crash the entity; it just yields no value."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="N/A", unit="W", connector_id=1)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert hass.states.get(entity_id).state == "unknown"


async def test_per_phase_samples_are_summed_when_no_total_is_reported(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """With only per-phase Power.Active.Import samples (no phaseless total), sum them."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(
        entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1000", unit="W", phase="L1", connector_id=1
    )
    record_meter_sample(
        entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1100", unit="W", phase="L2", connector_id=1
    )
    record_meter_sample(
        entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1200", unit="W", phase="L3", connector_id=1
    )
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert hass.states.get(entity_id).state == "3300.0"


async def test_total_sample_is_preferred_over_per_phase_samples(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A phaseless total sample wins over summing per-phase samples, if both are present."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(
        entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="1000", unit="W", phase="L1", connector_id=1
    )
    record_meter_sample(entry_data.app, measurand=MEASURAND_POWER_ACTIVE_IMPORT, value="2500", unit="W", connector_id=1)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_current_power_w"
    )
    assert hass.states.get(entity_id).state == "2500.0"
