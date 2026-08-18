"""Tests for `OccpChargePointStateSensor` (REQ-0019)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


async def test_status_maps_to_five_value_state_model(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """The raw OCPP status maps to the five-value state model, with discovery attributes."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CHARGE_POINT_ID}_1_charge_point_state")
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "not_connected"
    assert state.attributes["raw_ocpp_status"] == "Available"
    assert state.attributes["error_code"] is None

    entry_data.app.connectors.update(CHARGE_POINT_ID, 1, status="Charging", error_code=None)
    publish_state_change(entry_data.app, connector_id=1)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "charging"


async def test_faulted_status_maps_to_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A `Faulted` StatusNotification maps to the `error` state, with its error code as an attribute."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    entry_data.app.connectors.update(CHARGE_POINT_ID, 1, status="Faulted", error_code="GroundFailure")
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id("sensor", DOMAIN, f"{CHARGE_POINT_ID}_1_charge_point_state")
    state = hass.states.get(entity_id)
    assert state.state == "error"
    assert state.attributes["error_code"] == "GroundFailure"
