"""Tests for `Ocpp16PowerLimitNumber`."""

from collections.abc import Callable

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from custom_components.ocpp16.const import CONF_HOST, CONF_MAX_POWER_LIMIT_W, CONF_PORT, DOMAIN
from custom_components.ocpp16.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant, State
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{connector_identifier(entry_id, CHARGE_POINT_ID, 1)}_power_limit_w"
    entity_id = er.async_get(hass).async_get_entity_id("number", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_unknown_until_a_value_is_set(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`unknown` (optimistic, no live GetCompositeSchedule read) until set this session."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "unknown"


async def test_setting_a_value_sets_the_charging_profile(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A positive value sends `SetChargingProfile` and optimistically updates the state."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": 5000}, blocking=True)
    mock_charge_point_connection.set_charging_profile.assert_awaited_with(1, 1, 5000.0, None)
    assert hass.states.get(entity_id).state == "5000.0"


async def test_setting_zero_clears_the_charging_profile(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`0` is the "no limit" sentinel and sends `ClearChargingProfile` instead."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": 0}, blocking=True)
    mock_charge_point_connection.clear_charging_profile.assert_awaited_with(1)
    assert hass.states.get(entity_id).state == "0.0"


async def test_rejected_set_raises_and_leaves_state_unchanged(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A `Rejected` SetChargingProfile status surfaces as a `HomeAssistantError`, not a silent no-op."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    mock_charge_point_connection.set_charging_profile.return_value = "Rejected"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("number", "set_value", {"entity_id": entity_id, "value": 5000}, blocking=True)
    assert hass.states.get(entity_id).state == "unknown"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry with a non-default `max_power_limit_w` option."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OCPP (0.0.0.0:9000)",
        unique_id="0.0.0.0:9000",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9000},
        options={CONF_MAX_POWER_LIMIT_W: 11000.0},
    )


async def test_native_max_value_reflects_the_configured_option(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A non-default `max_power_limit_w` option is reflected on the entity, not a hardcoded ceiling."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    state = hass.states.get(entity_id)
    assert state.attributes["max"] == 11000.0


async def test_restores_the_last_set_value_across_a_restart(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_config_entry: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A HA restart restores the last successfully set value instead of showing `unknown` again."""
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("number.connector_1_power_limit", "5000.0"),
                {
                    "native_max_value": 22000.0,
                    "native_min_value": 0,
                    "native_step": 1.0,
                    "native_unit_of_measurement": "W",
                    "native_value": 5000.0,
                },
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_data = mock_config_entry.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, mock_config_entry.entry_id)
    assert hass.states.get(entity_id).state == "5000.0"
