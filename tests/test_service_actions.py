"""Tests for the 7 OCCP services in `service_actions/`."""

from collections.abc import Callable

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from custom_components.occp.entity_utils.device import connector_identifier
from custom_components.occp.service_actions.authorize_id_token import SERVICE_AUTHORIZE_ID_TOKEN
from custom_components.occp.service_actions.configuration import SERVICE_CHANGE_CONFIGURATION, SERVICE_GET_CONFIGURATION
from custom_components.occp.service_actions.power_limit import SERVICE_CLEAR_POWER_LIMIT, SERVICE_SET_POWER_LIMIT
from custom_components.occp.service_actions.reset import SERVICE_RESET
from custom_components.occp.service_actions.unlock_connector import SERVICE_UNLOCK_CONNECTOR
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr

CHARGE_POINT_ID = "CP001"


@pytest.fixture
async def booted_charge_point(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> tuple[str, str]:
    """Boot a charge point and return `(charge_point_device_id, connector_device_id)`."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    registry = dr.async_get(hass)
    charge_point_device = registry.async_get_device_by_identifier((DOMAIN, CHARGE_POINT_ID), init_integration.entry_id)
    connector_device = registry.async_get_device_by_identifier(
        (DOMAIN, connector_identifier(CHARGE_POINT_ID, 1)), init_integration.entry_id
    )
    assert charge_point_device is not None
    assert connector_device is not None
    return charge_point_device.id, connector_device.id


async def test_set_and_clear_power_limit(
    hass: HomeAssistant, booted_charge_point: tuple[str, str], mock_charge_point_connection
) -> None:
    """Fähigkeit 3/4: setting then clearing a connector's power limit."""
    _, connector_device_id = booted_charge_point

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_POWER_LIMIT,
        {"device_id": connector_device_id, "limit_w": 4000},
        blocking=True,
        return_response=True,
    )
    assert response == {"status": "accepted"}
    mock_charge_point_connection.set_charging_profile.assert_awaited_with(1, 1, 4000.0, None)

    response = await hass.services.async_call(
        DOMAIN, SERVICE_CLEAR_POWER_LIMIT, {"device_id": connector_device_id}, blocking=True, return_response=True
    )
    assert response == {"status": "accepted"}


async def test_authorize_id_token(hass: HomeAssistant, booted_charge_point: tuple[str, str]) -> None:
    """Fähigkeit 8: an unknown idTag returns a structured `invalid` response, not an exception."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTHORIZE_ID_TOKEN,
        {"charge_point_id": CHARGE_POINT_ID, "id_token": "UNKNOWN"},
        blocking=True,
        return_response=True,
    )
    assert response == {"authorized": False, "status": "invalid"}


async def test_reset(hass: HomeAssistant, booted_charge_point: tuple[str, str], mock_charge_point_connection) -> None:
    """`reset` targets the charge-point device, not a connector."""
    charge_point_device_id, _ = booted_charge_point

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET,
        {"device_id": charge_point_device_id, "reset_type": "Soft"},
        blocking=True,
        return_response=True,
    )
    assert response == {"accepted": True}
    mock_charge_point_connection.reset.assert_awaited_with("Soft")


async def test_unlock_connector(
    hass: HomeAssistant, booted_charge_point: tuple[str, str], mock_charge_point_connection
) -> None:
    """`unlock_connector` targets the connector device."""
    _, connector_device_id = booted_charge_point

    response = await hass.services.async_call(
        DOMAIN, SERVICE_UNLOCK_CONNECTOR, {"device_id": connector_device_id}, blocking=True, return_response=True
    )
    assert response == {"status": "Unlocked"}


async def test_get_and_change_configuration(
    hass: HomeAssistant, booted_charge_point: tuple[str, str], mock_charge_point_connection
) -> None:
    """`get_configuration`/`change_configuration` target the charge-point device."""
    charge_point_device_id, _ = booted_charge_point

    response = await hass.services.async_call(
        DOMAIN, SERVICE_GET_CONFIGURATION, {"device_id": charge_point_device_id}, blocking=True, return_response=True
    )
    assert response == {
        "entries": [{"key": "HeartbeatInterval", "value": "300", "readonly": False}],
        "unknown_keys": [],
    }

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CHANGE_CONFIGURATION,
        {"device_id": charge_point_device_id, "key": "HeartbeatInterval", "value": "250"},
        blocking=True,
        return_response=True,
    )
    assert response == {"status": "Accepted"}


async def test_unknown_device_raises_service_validation_error(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """REQ-0035 AC7: an unknown device is a `ServiceValidationError`, not an unhandled exception."""
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET,
            {"device_id": "nonexistent", "reset_type": "Soft"},
            blocking=True,
            return_response=True,
        )


async def test_connector_device_rejected_for_charge_point_only_service(
    hass: HomeAssistant, booted_charge_point: tuple[str, str]
) -> None:
    """`reset` requires the charge-point device itself, not a connector."""
    _, connector_device_id = booted_charge_point
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_RESET,
            {"device_id": connector_device_id, "reset_type": "Soft"},
            blocking=True,
            return_response=True,
        )


async def test_charge_point_device_rejected_for_connector_only_service(
    hass: HomeAssistant, booted_charge_point: tuple[str, str]
) -> None:
    """`unlock_connector` requires a connector device, not the charge-point device itself."""
    charge_point_device_id, _ = booted_charge_point
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UNLOCK_CONNECTOR,
            {"device_id": charge_point_device_id},
            blocking=True,
            return_response=True,
        )
