"""``Reset`` als HA-Service (kein REQ-0035-Vertragsbestandteil, siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_charge_point_device

SERVICE_RESET = "reset"

ATTR_RESET_TYPE = "reset_type"

_RESET_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_RESET_TYPE): vol.In(["Soft", "Hard"]),
    }
)


async def _handle_reset(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id = _resolve_charge_point_device(hass, call)
    try:
        result = await entry_data.app.command_service.reset(charge_point_id, call.data[ATTR_RESET_TYPE])
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    if not result.accepted:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="reset_rejected")
    return {"accepted": result.accepted}
