"""Tests for setup and unload of the occp integration."""

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant


async def test_setup_and_unload(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    """The entry loads and unloads cleanly."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED
