"""Tests for `OcppReconnectCountSensor`."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import charge_point_identifier
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{charge_point_identifier(entry_id, CHARGE_POINT_ID)}_reconnect_count"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_zero_after_the_first_connection(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """The very first connection for a charge point does not count as a reconnect."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "0"


async def test_increments_on_a_second_connection(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A second `register_connection` call for the same charge point counts as a reconnect."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "0"

    entry_data.app.registry.register_connection(CHARGE_POINT_ID, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "1"


async def test_restored_count_from_previous_runs_is_added_to_the_current_process_count(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_config_entry: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Unlike the transaction sensors, this is additive: a restart must not lose prior reconnects."""
    mock_config_entry.add_to_hass(hass)
    unique_id = f"{charge_point_identifier(mock_config_entry.entry_id, CHARGE_POINT_ID)}_reconnect_count"
    entity_id = (
        er.async_get(hass).async_get_or_create("sensor", DOMAIN, unique_id, config_entry=mock_config_entry).entity_id
    )
    mock_restore_cache_with_extra_data(
        hass, [(State(entity_id, "3"), {"native_value": 3, "native_unit_of_measurement": None})]
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_data = mock_config_entry.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "3"

    entry_data.app.registry.register_connection(CHARGE_POINT_ID, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "4"
