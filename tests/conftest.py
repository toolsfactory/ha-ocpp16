"""Shared fixtures for the occp tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import CONF_HOST, CONF_PORT, DOMAIN
from homeassistant.core import HomeAssistant


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations in every test."""


@pytest.fixture
def mock_app_start_stop() -> Generator[None]:
    """Patch `CentralSystemApp.start`/`stop` so setup never binds a real socket."""
    with (
        patch("custom_components.occp.core.app.CentralSystemApp.start", new_callable=AsyncMock),
        patch("custom_components.occp.core.app.CentralSystemApp.stop", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for this integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9000)",
        unique_id="0.0.0.0:9000",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9000},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration from a config entry.

    Returns:
        The config entry, now loaded.

    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
