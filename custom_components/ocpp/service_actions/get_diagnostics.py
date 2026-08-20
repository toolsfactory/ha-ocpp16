"""``GetDiagnostics`` als HA-Service (kein REQ-0035-Vertragsbestandteil, siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_charge_point_device

SERVICE_GET_DIAGNOSTICS = "get_diagnostics"

ATTR_LOCATION = "location"
ATTR_RETRIES = "retries"
ATTR_RETRY_INTERVAL = "retry_interval"
ATTR_START_TIME = "start_time"
ATTR_STOP_TIME = "stop_time"

_GET_DIAGNOSTICS_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_LOCATION): cv.string,
        vol.Optional(ATTR_RETRIES): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_RETRY_INTERVAL): vol.All(vol.Coerce(int), vol.Range(min=0)),
        vol.Optional(ATTR_START_TIME): cv.string,
        vol.Optional(ATTR_STOP_TIME): cv.string,
    }
)


async def _handle_get_diagnostics(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id = _resolve_charge_point_device(hass, call)
    try:
        result = await entry_data.app.command_service.get_diagnostics(
            charge_point_id,
            call.data[ATTR_LOCATION],
            retries=call.data.get(ATTR_RETRIES),
            retry_interval=call.data.get(ATTR_RETRY_INTERVAL),
            start_time=call.data.get(ATTR_START_TIME),
            stop_time=call.data.get(ATTR_STOP_TIME),
        )
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    # OCPP 1.6 kennt für GetDiagnostics.conf keinen Status (siehe commands.py) --
    # anders als reset/unlock_connector/change_configuration gibt es hier keinen
    # "rejected"-Zweig zu pruefen, ein CallError ist der einzige Fehlerpfad.
    return {"file_name": result.file_name}
