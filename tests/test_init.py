"""Tests for setup and unload of the ocpp16 integration."""

from collections.abc import Callable
from pathlib import Path
from unittest.mock import patch

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp16.const import CONF_CERTIFICATE_PATH, CONF_HOST, CONF_PORT, CONF_PRIVATE_KEY_PATH, DOMAIN
from custom_components.ocpp16.entity_utils.device import charge_point_identifier, connector_identifier
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


async def test_bind_failure_is_a_translated_config_entry_not_ready(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A port bind failure at setup time is a translated ConfigEntryNotReady, not a raw OS error."""
    mock_config_entry.add_to_hass(hass)

    with patch("custom_components.ocpp16.core.app.CentralSystemApp.start", side_effect=OSError("address in use")):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "bind_failed"


async def test_setup_wires_tls_certificate_into_app_config(
    hass: HomeAssistant, mock_app_start_stop: None, tls_cert_pair: tuple[Path, Path]
) -> None:
    """A configured certificate/key pair (Phase 5) reaches `AppConfig`, and setup succeeds."""
    cert_path, key_path = tls_cert_pair
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCPP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={
            CONF_HOST: "0.0.0.0",
            CONF_PORT: 9500,
            CONF_CERTIFICATE_PATH: str(cert_path),
            CONF_PRIVATE_KEY_PATH: str(key_path),
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert entry.runtime_data.app.config.certificate_path == cert_path
    assert entry.runtime_data.app.config.private_key_path == key_path


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
