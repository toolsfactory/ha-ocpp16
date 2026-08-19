"""``UnlockConnector`` als HA-Service (kein REQ-0035-Vertragsbestandteil, siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.occp.const import DOMAIN
from custom_components.occp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_single_connector_device

SERVICE_UNLOCK_CONNECTOR = "unlock_connector"

_UNLOCK_CONNECTOR_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})


async def _handle_unlock_connector(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id, connector_id = _resolve_single_connector_device(hass, call)
    try:
        result = await entry_data.app.command_service.unlock_connector(charge_point_id, connector_id)
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    if result.status != "Unlocked":
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="unlock_rejected",
            translation_placeholders={"status": result.status},
        )
    return {"status": result.status}
