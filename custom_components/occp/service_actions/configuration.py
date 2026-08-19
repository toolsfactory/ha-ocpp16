"""``GetConfiguration``/``ChangeConfiguration`` als HA-Services (siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.occp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_charge_point_device

SERVICE_GET_CONFIGURATION = "get_configuration"
SERVICE_CHANGE_CONFIGURATION = "change_configuration"

ATTR_KEYS = "keys"
ATTR_KEY = "key"
ATTR_VALUE = "value"

_GET_CONFIGURATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Optional(ATTR_KEYS): vol.All(cv.ensure_list, [cv.string]),
    }
)

_CHANGE_CONFIGURATION_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_KEY): cv.string,
        vol.Required(ATTR_VALUE): cv.string,
    }
)


async def _handle_get_configuration(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id = _resolve_charge_point_device(hass, call)
    try:
        result = await entry_data.app.command_service.get_configuration(charge_point_id, call.data.get(ATTR_KEYS))
    except CommandError as err:
        raise ServiceValidationError(str(err)) from err
    return {
        "entries": [{"key": entry.key, "value": entry.value, "readonly": entry.readonly} for entry in result.entries],
        "unknown_keys": list(result.unknown_keys),
    }


async def _handle_change_configuration(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id = _resolve_charge_point_device(hass, call)
    try:
        result = await entry_data.app.command_service.change_configuration(
            charge_point_id, call.data[ATTR_KEY], call.data[ATTR_VALUE]
        )
    except CommandError as err:
        raise ServiceValidationError(str(err)) from err
    return {"status": result.status}
