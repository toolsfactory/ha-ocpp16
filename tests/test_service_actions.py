"""Tests for the 7 OCCP services in `service_actions/`."""

from collections.abc import Callable
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import CONF_HOST, CONF_PORT, DOMAIN
from custom_components.occp.core.domain.authorization import StaticAuthorizationProvider, StaticIdTagEntry
from custom_components.occp.entity_utils.device import charge_point_identifier, connector_identifier
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
    charge_point_device = registry.async_get_device_by_identifier(
        (DOMAIN, charge_point_identifier(init_integration.entry_id, CHARGE_POINT_ID)), init_integration.entry_id
    )
    connector_device = registry.async_get_device_by_identifier(
        (DOMAIN, connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)), init_integration.entry_id
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


async def test_service_call_reaches_the_device_s_own_entry_not_the_first_loaded_one(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    booted_charge_point: tuple[str, str],
    mock_charge_point_connection: AsyncMock,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Two entries whose registries both know `CHARGE_POINT_ID` -- the call must reach the right one.

    Regression test for a bug where the resolver searched every loaded entry
    for a matching `charge_point_id` and used whichever loaded first, instead
    of the entry that actually owns the resolved device.
    """
    charge_point_device_id, _ = booted_charge_point

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="second-entry-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
    )
    second_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()

    second_connection = AsyncMock()
    second_connection.reset.return_value = "Accepted"
    boot_charge_point(second_entry.runtime_data.app, second_connection, charge_point_id=CHARGE_POINT_ID)
    publish_state_change(second_entry.runtime_data.app, charge_point_id=CHARGE_POINT_ID, connector_id=None)
    await hass.async_block_till_done()

    second_charge_point_device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, charge_point_identifier(second_entry.entry_id, CHARGE_POINT_ID)), second_entry.entry_id
    )
    assert second_charge_point_device is not None
    assert second_charge_point_device.id != charge_point_device_id

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_RESET,
        {"device_id": second_charge_point_device.id, "reset_type": "Soft"},
        blocking=True,
        return_response=True,
    )
    assert response == {"accepted": True}
    second_connection.reset.assert_awaited_with("Soft")
    mock_charge_point_connection.reset.assert_not_awaited()


async def test_authorize_id_token_with_device_id_scopes_to_the_correct_entry(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    init_integration: MockConfigEntry,
    booted_charge_point: tuple[str, str],
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """`device_id` disambiguates two entries that both know the same `charge_point_id`.

    Regression test for the residual ambiguity `_find_entry_data()` still has when no
    `device_id` is given: it returns whichever loaded entry it scans first. Passing
    `device_id` must reach that device's own entry instead.
    """
    charge_point_device_id, _ = booted_charge_point
    init_integration.runtime_data.app.authorization = StaticAuthorizationProvider(
        [StaticIdTagEntry(id_tag="FIRST-ENTRY-TAG")]
    )

    second_entry = MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9500)",
        unique_id="second-entry-uuid",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9500},
    )
    second_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(second_entry.entry_id)
    await hass.async_block_till_done()
    second_entry.runtime_data.app.authorization = StaticAuthorizationProvider(
        [StaticIdTagEntry(id_tag="SECOND-ENTRY-TAG")]
    )

    boot_charge_point(second_entry.runtime_data.app, AsyncMock(), charge_point_id=CHARGE_POINT_ID)
    publish_state_change(second_entry.runtime_data.app, charge_point_id=CHARGE_POINT_ID, connector_id=None)
    await hass.async_block_till_done()

    second_charge_point_device = dr.async_get(hass).async_get_device_by_identifier(
        (DOMAIN, charge_point_identifier(second_entry.entry_id, CHARGE_POINT_ID)), second_entry.entry_id
    )
    assert second_charge_point_device is not None

    # Without device_id: the existing scan-and-take-first-match behavior (documented, not
    # fixed here) reaches the first-loaded entry regardless of which idTag we ask about.
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTHORIZE_ID_TOKEN,
        {"charge_point_id": CHARGE_POINT_ID, "id_token": "SECOND-ENTRY-TAG"},
        blocking=True,
        return_response=True,
    )
    assert response == {"authorized": False, "status": "invalid"}

    # With device_id: scoped to the exact entry that owns the device, regardless of scan order.
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTHORIZE_ID_TOKEN,
        {
            "charge_point_id": CHARGE_POINT_ID,
            "id_token": "SECOND-ENTRY-TAG",
            "device_id": second_charge_point_device.id,
        },
        blocking=True,
        return_response=True,
    )
    assert response == {"authorized": True, "status": "accepted"}

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_AUTHORIZE_ID_TOKEN,
        {"charge_point_id": CHARGE_POINT_ID, "id_token": "FIRST-ENTRY-TAG", "device_id": charge_point_device_id},
        blocking=True,
        return_response=True,
    )
    assert response == {"authorized": True, "status": "accepted"}
