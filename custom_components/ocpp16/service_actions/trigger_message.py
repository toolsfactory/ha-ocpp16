"""``TriggerMessage`` als HA-Service (kein REQ-0035-Vertragsbestandteil, siehe Package-Docstring)."""

import voluptuous as vol

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv

from ._resolvers import _resolve_charge_point_device

SERVICE_TRIGGER_MESSAGE = "trigger_message"

ATTR_REQUESTED_MESSAGE = "requested_message"

# OCPP 1.6 core MessageTrigger values only -- die beiden Security-Whitepaper-
# Erweiterungen (LogStatusNotification, SignChargePointCertificate) unterstützt
# dieses Projekt sonst nirgends, siehe Plan.
_REQUESTED_MESSAGES = (
    "BootNotification",
    "DiagnosticsStatusNotification",
    "FirmwareStatusNotification",
    "Heartbeat",
    "MeterValues",
    "StatusNotification",
)

_TRIGGER_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_REQUESTED_MESSAGE): vol.In(_REQUESTED_MESSAGES),
    }
)


async def _handle_trigger_message(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    entry_data, charge_point_id = _resolve_charge_point_device(hass, call)
    try:
        result = await entry_data.app.command_service.trigger_message(
            charge_point_id, call.data[ATTR_REQUESTED_MESSAGE]
        )
    except CommandError as err:
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="command_rejected", translation_placeholders={"error": str(err)}
        ) from err
    # Anders als reset/unlock_connector/change_configuration ändert
    # trigger_message keinen Charge-Point-Zustand -- "Rejected"/"NotImplemented"
    # ist eine informative Antwort ("unterstützt diese Nachricht nicht"), keine
    # fehlgeschlagene Aktion, daher hier bewusst kein Raise (siehe Plan).
    return {"status": result.status}
