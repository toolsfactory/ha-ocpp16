"""Tests for setup and unload of the occp integration."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from custom_components.occp.entity_utils.device import charge_point_identifier, connector_identifier
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

CHARGE_POINT_ID = "CP001"

_ALL_SERVICES = (
    "set_power_limit",
    "clear_power_limit",
    "authorize_id_token",
    "reset",
    "unlock_connector",
    "get_configuration",
    "change_configuration",
)


async def test_setup_and_unload(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The entry loads and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


async def test_device_names_are_language_neutral(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Device names use plain English, not the leftover German dev-language defaults."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    charge_point_device = registry.async_get_device_by_identifier(
        (DOMAIN, charge_point_identifier(init_integration.entry_id, CHARGE_POINT_ID)), init_integration.entry_id
    )
    connector_device = registry.async_get_device_by_identifier(
        (DOMAIN, connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)), init_integration.entry_id
    )
    assert charge_point_device.name == f"Charge Point {CHARGE_POINT_ID}"
    assert connector_device.name == "Connector 1"


async def test_services_survive_reload_of_the_only_loaded_entry(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """Reloading the only loaded entry must not leave the domain's services unregistered."""
    for service in _ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, service)

    assert await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.LOADED

    for service in _ALL_SERVICES:
        assert hass.services.has_service(DOMAIN, service)
