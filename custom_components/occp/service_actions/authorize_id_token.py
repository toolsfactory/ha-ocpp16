"""Fähigkeit 8 des Interop-Vertrags: idTag-Autorisierung prüfen (REQ-0035)."""

import voluptuous as vol

from custom_components.occp.const import DOMAIN
from custom_components.occp.utils import interop
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _entry_data_for_device, _find_entry_data, _get_device_entry

SERVICE_AUTHORIZE_ID_TOKEN = "authorize_id_token"

ATTR_CHARGE_POINT_ID = "charge_point_id"
ATTR_ID_TOKEN = "id_token"

_AUTHORIZE_ID_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHARGE_POINT_ID): cv.string,
        vol.Required(ATTR_ID_TOKEN): cv.string,
        vol.Optional(ATTR_DEVICE_ID): cv.string,
    }
)


async def _handle_authorize_id_token(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id = call.data[ATTR_CHARGE_POINT_ID]

    if ATTR_DEVICE_ID in call.data:
        # Ein device_id-Wert scopt eindeutig auf einen Config Entry -- vermeidet die
        # Mehrdeutigkeit von _find_entry_data() bei zwei Instanzen mit zufällig
        # identischer charge_point_id (siehe DECISIONS.md). Optional statt
        # verpflichtend: additiv, kein Breaking Change am bestehenden Aufrufschema.
        entry_data = _entry_data_for_device(hass, _get_device_entry(hass, call))
    else:
        entry_data = _find_entry_data(hass, charge_point_id)
        if entry_data is None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="unknown_charge_point",
                translation_placeholders={"charge_point_id": charge_point_id},
            )
    return interop.authorize_id_token(entry_data.app.authorization, call.data[ATTR_ID_TOKEN])
