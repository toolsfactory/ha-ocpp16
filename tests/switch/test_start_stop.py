"""Tests for `OccpStartStopSwitch` (REQ-0020)."""

from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import CONF_DEFAULT_ID_TAG, CONF_HOST, CONF_PORT, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry with a default idTag configured, needed for `async_turn_on`."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9000)",
        unique_id="0.0.0.0:9000",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9000},
        options={CONF_DEFAULT_ID_TAG: "TAG1"},
    )


def _get_entity_id(hass: HomeAssistant) -> str:
    entity_id = er.async_get(hass).async_get_entity_id("switch", DOMAIN, f"{CHARGE_POINT_ID}_1_start_stop")
    assert entity_id is not None
    return entity_id


async def test_turn_on_starts_a_transaction(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """An accepted RemoteStartTransaction turns the switch on."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass)
    assert hass.states.get(entity_id).state == "off"

    await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    mock_charge_point_connection.remote_start_transaction.assert_awaited_with(1, "TAG1")


async def test_turn_on_without_default_id_tag_raises(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """No configured default idTag is a clear configuration error, not a silent no-op (REQ-0020)."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9000)",
        unique_id="0.0.0.0:9000",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9000},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    entry_data = entry.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)


async def test_turn_on_rejected_by_charge_point_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A `Rejected` RemoteStartTransaction status surfaces as a HomeAssistantError, not a silent no-op."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass)

    mock_charge_point_connection.remote_start_transaction.return_value = "Rejected"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id}, blocking=True)
    assert hass.states.get(entity_id).state == "off"


async def test_turn_off_stops_the_active_transaction(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`turn_off` stops the connector's active transaction."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    transaction = entry_data.app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID,
        connector_id=1,
        id_tag="TAG1",
        meter_start_wh=0,
        started_at=datetime.now(UTC),
    )
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass)
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    mock_charge_point_connection.remote_stop_transaction.assert_awaited_with(transaction.transaction_id)
