"""Tests for setup and unload of the occp integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

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
