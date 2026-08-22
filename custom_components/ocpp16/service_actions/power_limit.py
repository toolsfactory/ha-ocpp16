"""Fähigkeit 3/4 des Interop-Vertrags: Leistungsgrenze setzen/löschen (REQ-0035)."""

import voluptuous as vol

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.core.domain.commands import CommandError
from custom_components.ocpp16.utils import interop
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_single_connector_device

SERVICE_SET_POWER_LIMIT = "set_power_limit"
SERVICE_CLEAR_POWER_LIMIT = "clear_power_limit"

ATTR_LIMIT_W = "limit_w"
ATTR_PHASES = "phases"

_SET_POWER_LIMIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_LIMIT_W): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
        vol.Optional(ATTR_PHASES): vol.All(vol.Coerce(int), vol.In([1, 2, 3])),
    }
)

_CLEAR_POWER_LIMIT_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


async def _handle_set_power_limit(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id, connector_id = _resolve_single_connector_device(hass, call)
    try:
        result = await interop.set_power_limit(
            entry_data.app.command_service,
            charge_point_id,
            connector_id,
            call.data[ATTR_LIMIT_W],
            call.data.get(ATTR_PHASES),
        )
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    if result["status"] != "accepted":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="power_limit_rejected",
            translation_placeholders={"status": result["status"]},
        )
    return result


async def _handle_clear_power_limit(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id, connector_id = _resolve_single_connector_device(hass, call)
    try:
        result = await interop.clear_power_limit(entry_data.app.command_service, charge_point_id, connector_id)
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    if result["status"] != "accepted":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="power_limit_rejected",
            translation_placeholders={"status": result["status"]},
        )
    return result
