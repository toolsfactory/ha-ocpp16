"""Tests for `OcppLastStopReasonSensor`."""

from collections.abc import Callable
from datetime import UTC, datetime

from pytest_homeassistant_custom_component.common import MockConfigEntry, mock_restore_cache_with_extra_data

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{connector_identifier(entry_id, CHARGE_POINT_ID, 1)}_last_stop_reason"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_unknown_while_no_session_has_stopped(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`unknown` before any transaction and while one is still active on this connector."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "unknown"

    transaction = entry_data.app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID,
        connector_id=1,
        id_tag="TAG1",
        meter_start_wh=0,
        started_at=datetime.now(UTC),
    )
    publish_state_change(entry_data.app, connector_id=1, transaction_id=transaction.transaction_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "unknown"


async def test_populates_on_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """The raw OCPP stop reason populates once the transaction stops."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    transaction = entry_data.app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID,
        connector_id=1,
        id_tag="TAG1",
        meter_start_wh=0,
        started_at=datetime.now(UTC),
    )
    entry_data.app.transactions.stop_transaction(
        transaction.transaction_id, meter_stop_wh=1000, stopped_at=datetime.now(UTC), reason="EVDisconnected"
    )
    publish_state_change(entry_data.app, connector_id=1, transaction_id=transaction.transaction_id)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "EVDisconnected"


async def test_restores_the_last_known_value_across_a_restart(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_config_entry: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A HA restart restores the last known stop reason until this run sees a transaction."""
    mock_config_entry.add_to_hass(hass)
    unique_id = f"{connector_identifier(mock_config_entry.entry_id, CHARGE_POINT_ID, 1)}_last_stop_reason"
    entity_id = (
        er.async_get(hass).async_get_or_create("sensor", DOMAIN, unique_id, config_entry=mock_config_entry).entity_id
    )
    mock_restore_cache_with_extra_data(
        hass,
        [(State(entity_id, "EVDisconnected"), {"native_value": "EVDisconnected", "native_unit_of_measurement": None})],
    )
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entry_data = mock_config_entry.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "EVDisconnected"
