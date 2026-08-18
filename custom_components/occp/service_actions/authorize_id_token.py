"""Fähigkeit 8 des Interop-Vertrags: idTag-Autorisierung prüfen (REQ-0035)."""

import voluptuous as vol

from custom_components.occp.utils import interop
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _find_entry_data

SERVICE_AUTHORIZE_ID_TOKEN = "authorize_id_token"

ATTR_CHARGE_POINT_ID = "charge_point_id"
ATTR_ID_TOKEN = "id_token"

_AUTHORIZE_ID_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHARGE_POINT_ID): cv.string,
        vol.Required(ATTR_ID_TOKEN): cv.string,
    }
)


async def _handle_authorize_id_token(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id = call.data[ATTR_CHARGE_POINT_ID]
    entry_data = _find_entry_data(hass, charge_point_id)
    if entry_data is None:
        raise ServiceValidationError(f"Unbekannter Ladepunkt '{charge_point_id}'.")
    return interop.authorize_id_token(entry_data.app.authorization, call.data[ATTR_ID_TOKEN])
