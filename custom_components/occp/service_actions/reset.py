"""``Reset`` als HA-Service (kein REQ-0035-Vertragsbestandteil, siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.occp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _find_entry_data, _resolve_charge_point_device

SERVICE_RESET = "reset"

ATTR_RESET_TYPE = "reset_type"

_RESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_RESET_TYPE): vol.In(["Soft", "Hard"]),
    }
)


async def _handle_reset(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id = _resolve_charge_point_device(hass, call)
    entry_data = _find_entry_data(hass, charge_point_id)
    if entry_data is None:
        raise ServiceValidationError(f"Unbekannter Ladepunkt '{charge_point_id}'.")
    try:
        result = await entry_data.app.command_service.reset(charge_point_id, call.data[ATTR_RESET_TYPE])
    except CommandError as err:
        raise ServiceValidationError(str(err)) from err
    return {"accepted": result.accepted}
