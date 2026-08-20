"""Tests for `OcppResetButton`."""

from collections.abc import Callable

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import charge_point_identifier
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


def _get_entity_id(hass: HomeAssistant, entry_id: str) -> str:
    unique_id = f"{charge_point_identifier(entry_id, CHARGE_POINT_ID)}_reset"
    entity_id = er.async_get(hass).async_get_entity_id("button", DOMAIN, unique_id)
    assert entity_id is not None
    return entity_id


async def test_press_sends_a_soft_reset(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Pressing the button always sends `Soft`, never `Hard` (confirmed with the developer)."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
    mock_charge_point_connection.reset.assert_awaited_with("Soft")


async def test_rejected_reset_raises(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A `Rejected` Reset status surfaces as a `HomeAssistantError`, not a silent no-op."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    entity_id = _get_entity_id(hass, init_integration.entry_id)

    mock_charge_point_connection.reset.return_value = "Rejected"
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call("button", "press", {"entity_id": entity_id}, blocking=True)
