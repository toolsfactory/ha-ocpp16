"""Tests for `OcppLastTransactionIdSensor`."""

from collections.abc import Callable
from datetime import UTC, datetime

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{connector_identifier(entry_id, CHARGE_POINT_ID, 1)}_last_transaction_id"
    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_unknown_until_a_transaction_starts(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`unknown` until this connector's first transaction ever starts."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "unknown"


async def test_updates_on_start_and_survives_stop(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """The transaction id populates on start and stays visible after the transaction stops."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    transaction = entry_data.app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID,
        connector_id=1,
        id_tag="TAG1",
        meter_start_wh=0,
        started_at=datetime.now(UTC),
    )
    publish_state_change(entry_data.app, connector_id=1, transaction_id=transaction.transaction_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == str(transaction.transaction_id)

    entry_data.app.transactions.stop_transaction(
        transaction.transaction_id, meter_stop_wh=1000, stopped_at=datetime.now(UTC), reason="Local"
    )
    publish_state_change(entry_data.app, connector_id=1, transaction_id=transaction.transaction_id)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == str(transaction.transaction_id)
