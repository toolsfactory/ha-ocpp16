"""Tests for `OcppAvailabilitySwitch` (Fähigkeit 6, REQ-0021, ADR-0009)."""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{connector_identifier(entry_id, CHARGE_POINT_ID, 1)}_availability"
    entity_id = er.async_get(hass).async_get_entity_id("switch", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_turn_off_sends_change_availability_inoperative(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`turn_off` sends `ChangeAvailability(Inoperative)`; an `Accepted` status turns the switch off immediately."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)
    assert hass.states.get(entity_id).state == "on"

    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)
    mock_charge_point_connection.change_availability.assert_awaited_with(1, "Inoperative")


async def test_scheduled_status_does_not_flip_the_reported_state(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """REQ-0021 AC2: a `Scheduled` response is exposed as an attribute, not an immediate state change.

    The switch's actual on/off state comes exclusively from the next
    StatusNotification (ADR-0009) -- not synthesized from the ChangeAvailability
    response.
    """
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    mock_charge_point_connection.change_availability.return_value = "Scheduled"
    await hass.services.async_call("switch", "turn_off", {"entity_id": entity_id}, blocking=True)

    state = hass.states.get(entity_id)
    assert state.state == "on"
    assert state.attributes["last_change_status"] == "Scheduled"
    assert state.attributes["change_pending"] is True
