"""HA-Services für die Interop-Vertrag-Fähigkeiten 3, 4, 8 (REQ-0035, ADR-0010).

Fähigkeit 3/4 (``set_power_limit``/``clear_power_limit``) sind
Device-targeted Services (Ziel-Connector über die HA-Device-Registry, siehe
``device.py``); Fähigkeit 8 (``authorize_id_token``) trägt ``charge_point_id``
bereits als Vertrags-Pflichtfeld.

REQ-0035 AC7 ("unbekannter/nicht verbundener Ladepunkt -> erkennbare
Fehlerantwort, keine Exception ohne strukturierte Rückmeldung"): alle drei
Handler werfen dafür ``homeassistant.exceptions.ServiceValidationError`` --
laut ADR-0010 die in Home Assistant vorgesehene, strukturierte Fehlerform für
ungültige Aufrufparameter (HA stellt sie strukturiert im Frontend/
``supports_response``-Ergebnis dar).
"""

import functools

import voluptuous as vol

from custom_components.occp.core.domain.commands import CommandError
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr

from . import interop
from .const import DOMAIN
from .device import parse_connector_identifier
from .runtime import OccpEntryData

SERVICE_SET_POWER_LIMIT = "set_power_limit"
SERVICE_CLEAR_POWER_LIMIT = "clear_power_limit"
SERVICE_AUTHORIZE_ID_TOKEN = "authorize_id_token"

ATTR_LIMIT_W = "limit_w"
ATTR_PHASES = "phases"
ATTR_CHARGE_POINT_ID = "charge_point_id"
ATTR_ID_TOKEN = "id_token"

_SET_POWER_LIMIT_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_DEVICE_ID): cv.string,
        vol.Required(ATTR_LIMIT_W): vol.All(vol.Coerce(float), vol.Range(min=0.01)),
        vol.Optional(ATTR_PHASES): vol.All(vol.Coerce(int), vol.In([1, 2, 3])),
    }
)

_CLEAR_POWER_LIMIT_SCHEMA = vol.Schema({vol.Required(ATTR_DEVICE_ID): cv.string})

_AUTHORIZE_ID_TOKEN_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CHARGE_POINT_ID): cv.string,
        vol.Required(ATTR_ID_TOKEN): cv.string,
    }
)


def _resolve_single_connector_device(hass: HomeAssistant, call: ServiceCall) -> tuple[str, int]:
    device_id: str = call.data[ATTR_DEVICE_ID]
    registry = dr.async_get(hass)
    device_entry = registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(f"Unbekanntes Gerät '{device_id}'.")

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        parsed = parse_connector_identifier(identifier)
        if parsed is not None:
            return parsed

    raise ServiceValidationError(
        f"Gerät '{device_id}' ist kein OCCP-Connector (sondern z. B. die "
        "Ladestation selbst) -- dieser Service benötigt ein Connector-Gerät."
    )


def _find_entry_data(hass: HomeAssistant, charge_point_id: str) -> OccpEntryData | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entry_data = entry.runtime_data
        if entry_data.app.registry.get(charge_point_id) is not None:
            return entry_data
    return None


async def _handle_set_power_limit(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id, connector_id = _resolve_single_connector_device(hass, call)
    entry_data = _find_entry_data(hass, charge_point_id)
    if entry_data is None:
        raise ServiceValidationError(f"Unbekannter Ladepunkt '{charge_point_id}'.")
    try:
        return await interop.set_power_limit(
            entry_data.app.command_service,
            charge_point_id,
            connector_id,
            call.data[ATTR_LIMIT_W],
            call.data.get(ATTR_PHASES),
        )
    except CommandError as err:
        raise ServiceValidationError(str(err)) from err


async def _handle_clear_power_limit(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id, connector_id = _resolve_single_connector_device(hass, call)
    entry_data = _find_entry_data(hass, charge_point_id)
    if entry_data is None:
        raise ServiceValidationError(f"Unbekannter Ladepunkt '{charge_point_id}'.")
    try:
        return await interop.clear_power_limit(entry_data.app.command_service, charge_point_id, connector_id)
    except CommandError as err:
        raise ServiceValidationError(str(err)) from err


async def _handle_authorize_id_token(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    charge_point_id = call.data[ATTR_CHARGE_POINT_ID]
    entry_data = _find_entry_data(hass, charge_point_id)
    if entry_data is None:
        raise ServiceValidationError(f"Unbekannter Ladepunkt '{charge_point_id}'.")
    return interop.authorize_id_token(entry_data.app.authorization, call.data[ATTR_ID_TOKEN])


def async_register_services(hass: HomeAssistant) -> None:
    """Registriert die drei REQ-0035-Services genau einmal.

    Unabhängig von der Anzahl der Config Entries (Services sind Domain-,
    nicht Entry-gebunden, siehe interop-contract.md "Service-Domain-Konvention").
    """
    if hass.services.has_service(DOMAIN, SERVICE_SET_POWER_LIMIT):
        return

    # functools.partial statt lambda: HA erkennt den Service-Handler nur dann
    # korrekt als Coroutine-Funktion (und awaitet ihn selbst, statt eine
    # nie awaitete Coroutine zurückzubekommen), wenn `asyncio.iscoroutinefunction`
    # darauf zutrifft -- eine Lambda, die intern eine Coroutine zurückgibt,
    # ist selbst KEINE Coroutine-Funktion; ein `partial` einer `async def`
    # bleibt hingegen als solche erkennbar.
    hass.services.async_register(
        DOMAIN,
        SERVICE_SET_POWER_LIMIT,
        functools.partial(_handle_set_power_limit, hass),
        schema=_SET_POWER_LIMIT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_CLEAR_POWER_LIMIT,
        functools.partial(_handle_clear_power_limit, hass),
        schema=_CLEAR_POWER_LIMIT_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_AUTHORIZE_ID_TOKEN,
        functools.partial(_handle_authorize_id_token, hass),
        schema=_AUTHORIZE_ID_TOKEN_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


def async_unregister_services(hass: HomeAssistant) -> None:
    """Gegenstück zu ``async_register_services``.

    Wird aufgerufen, sobald der letzte Config Entry entladen wurde (siehe ``__init__.py``).
    """
    for service in (
        SERVICE_SET_POWER_LIMIT,
        SERVICE_CLEAR_POWER_LIMIT,
        SERVICE_AUTHORIZE_ID_TOKEN,
    ):
        hass.services.async_remove(DOMAIN, service)
