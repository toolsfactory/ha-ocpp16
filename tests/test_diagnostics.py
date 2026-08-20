"""Tests for `diagnostics.py` (Quality Scale rule `diagnostics`)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp.const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, CONF_HOST, CONF_PORT, DOMAIN
from custom_components.ocpp.diagnostics import async_get_config_entry_diagnostics
from homeassistant.components.diagnostics import REDACTED
from homeassistant.core import HomeAssistant

CHARGE_POINT_ID = "CP001"


async def test_diagnostics_redacts_sensitive_fields(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    tmp_path,
) -> None:
    """Host, authorization file path, and default idTag are redacted; nothing else is."""
    auth_file = tmp_path / "auth.json"
    auth_file.write_text('{"idTags": {"SECRET-TAG": {}}}', encoding="utf-8")

    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCPP (0.0.0.0:9500)",
        unique_id="existing-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
        options={CONF_AUTHORIZATION_FILE: str(auth_file), CONF_DEFAULT_ID_TAG: "SECRET-TAG"},
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    boot_charge_point(entry.runtime_data.app, mock_charge_point_connection)

    diagnostics = await async_get_config_entry_diagnostics(hass, entry)

    assert diagnostics["entry_data"][CONF_HOST] == REDACTED
    assert diagnostics["entry_options"][CONF_AUTHORIZATION_FILE] == REDACTED
    assert diagnostics["entry_options"][CONF_DEFAULT_ID_TAG] == REDACTED
    assert diagnostics["default_id_tag_configured"] is True

    assert diagnostics["charge_point_count"] == 1
    charge_point = diagnostics["charge_points"][0]
    assert charge_point["charge_point_id"] == CHARGE_POINT_ID
    assert charge_point["vendor"] == "Test-Vendor"
    # boot_charge_point registers connector 0 (charge-point-wide) plus connector 1.
    assert len(charge_point["connectors"]) == 2
    assert all(connector["status"] == "Available" for connector in charge_point["connectors"])


async def test_diagnostics_with_no_connected_charge_points(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """An entry with nothing connected yet still returns a valid, empty summary."""
    diagnostics = await async_get_config_entry_diagnostics(hass, init_integration)

    assert diagnostics["charge_point_count"] == 0
    assert diagnostics["charge_points"] == []
    assert diagnostics["default_id_tag_configured"] is False
