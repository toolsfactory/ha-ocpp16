"""Tests for `Ocpp16ActivePhasesSensor` (new, not part of the REQ-0035 interop contract)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{connector_identifier(entry_id, CHARGE_POINT_ID, 1)}_active_phases"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_no_current_reported_yet(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """No `Current.Import` samples at all -> zero active phases, all attributes `None`."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    state = hass.states.get(_get_entity_id(hass, init_integration.entry_id))
    assert state.state == "0"
    assert state.attributes["phase_l1_a"] is None
    assert state.attributes["phase_l2_a"] is None
    assert state.attributes["phase_l3_a"] is None


async def test_three_active_phases(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """Three phases reporting nonzero current -> count 3, values exposed as attributes."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, measurand="Current.Import", value="6.1", unit="A", phase="L1")
    record_meter_sample(entry_data.app, measurand="Current.Import", value="6.2", unit="A", phase="L2")
    record_meter_sample(entry_data.app, measurand="Current.Import", value="6.3", unit="A", phase="L3")
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    state = hass.states.get(_get_entity_id(hass, init_integration.entry_id))
    assert state.state == "3"
    assert state.attributes["phase_l1_a"] == 6.1
    assert state.attributes["phase_l2_a"] == 6.2
    assert state.attributes["phase_l3_a"] == 6.3


async def test_zero_current_phase_does_not_count_as_active(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
    record_meter_sample: Callable[..., None],
) -> None:
    """A phase reporting 0 A is present but not counted as active."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    record_meter_sample(entry_data.app, measurand="Current.Import", value="6.0", unit="A", phase="L1")
    record_meter_sample(entry_data.app, measurand="Current.Import", value="0", unit="A", phase="L2")
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    state = hass.states.get(_get_entity_id(hass, init_integration.entry_id))
    assert state.state == "1"
    assert state.attributes["phase_l1_a"] == 6.0
    assert state.attributes["phase_l2_a"] == 0.0
    assert state.attributes["phase_l3_a"] is None
