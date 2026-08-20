"""HA-Services für die Interop-Vertrag-Fähigkeiten 3, 4, 8 (REQ-0035, ADR-0010) plus reset/unlock_connector/get_configuration/change_configuration.

Die letzten vier waren im Kern (``CommandService``, ``core/domain/commands.py``)
und in der Standalone-Konsole (``core/console.py``) bereits vorhanden, aber nie
als HA-Service exponiert -- kein REQ-0035-Vertragsbestandteil, sondern eine in
dieser Session nachgezogene Scope-Entscheidung des Entwicklers.

Fähigkeit 3/4 (``set_power_limit``/``clear_power_limit``) sowie
``unlock_connector`` sind Device-targeted Services (Ziel-Connector über die
HA-Device-Registry, siehe ``entity_utils/device.py``); ``reset``/
``get_configuration``/``change_configuration`` zielen auf das Charge-Point-
Gerät selbst (nicht auf einen Connector); Fähigkeit 8 (``authorize_id_token``)
trägt ``charge_point_id`` bereits als Vertrags-Pflichtfeld.

REQ-0035 AC7 ("unbekannter/nicht verbundener Ladepunkt -> erkennbare
Fehlerantwort, keine Exception ohne strukturierte Rückmeldung"), analog auch
für die vier neuen Services angewendet: alle Handler werfen dafür
``homeassistant.exceptions.ServiceValidationError`` -- laut ADR-0010 die in
Home Assistant vorgesehene, strukturierte Fehlerform für ungültige
Aufrufparameter (HA stellt sie strukturiert im Frontend/
``supports_response``-Ergebnis dar).
"""

from collections.abc import Callable, Coroutine
import functools
from typing import Any

import voluptuous as vol

from custom_components.ocpp.const import DOMAIN
from homeassistant.core import HomeAssistant, ServiceCall, ServiceResponse, SupportsResponse

from .authorize_id_token import _AUTHORIZE_ID_TOKEN_SCHEMA, SERVICE_AUTHORIZE_ID_TOKEN, _handle_authorize_id_token
from .configuration import (
    _CHANGE_CONFIGURATION_SCHEMA,
    _GET_CONFIGURATION_SCHEMA,
    SERVICE_CHANGE_CONFIGURATION,
    SERVICE_GET_CONFIGURATION,
    _handle_change_configuration,
    _handle_get_configuration,
)
from .get_diagnostics import _GET_DIAGNOSTICS_SCHEMA, SERVICE_GET_DIAGNOSTICS, _handle_get_diagnostics
from .power_limit import (
    _CLEAR_POWER_LIMIT_SCHEMA,
    _SET_POWER_LIMIT_SCHEMA,
    SERVICE_CLEAR_POWER_LIMIT,
    SERVICE_SET_POWER_LIMIT,
    _handle_clear_power_limit,
    _handle_set_power_limit,
)
from .reset import _RESET_SCHEMA, SERVICE_RESET, _handle_reset
from .trigger_message import _TRIGGER_MESSAGE_SCHEMA, SERVICE_TRIGGER_MESSAGE, _handle_trigger_message
from .unlock_connector import _UNLOCK_CONNECTOR_SCHEMA, SERVICE_UNLOCK_CONNECTOR, _handle_unlock_connector

__all__ = ["async_register_services"]

_ServiceHandler = Callable[[HomeAssistant, ServiceCall], Coroutine[Any, Any, ServiceResponse]]

_SERVICES: tuple[tuple[str, vol.Schema, _ServiceHandler], ...] = (
    (SERVICE_SET_POWER_LIMIT, _SET_POWER_LIMIT_SCHEMA, _handle_set_power_limit),
    (SERVICE_CLEAR_POWER_LIMIT, _CLEAR_POWER_LIMIT_SCHEMA, _handle_clear_power_limit),
    (SERVICE_AUTHORIZE_ID_TOKEN, _AUTHORIZE_ID_TOKEN_SCHEMA, _handle_authorize_id_token),
    (SERVICE_RESET, _RESET_SCHEMA, _handle_reset),
    (SERVICE_UNLOCK_CONNECTOR, _UNLOCK_CONNECTOR_SCHEMA, _handle_unlock_connector),
    (SERVICE_GET_CONFIGURATION, _GET_CONFIGURATION_SCHEMA, _handle_get_configuration),
    (SERVICE_CHANGE_CONFIGURATION, _CHANGE_CONFIGURATION_SCHEMA, _handle_change_configuration),
    (SERVICE_TRIGGER_MESSAGE, _TRIGGER_MESSAGE_SCHEMA, _handle_trigger_message),
    (SERVICE_GET_DIAGNOSTICS, _GET_DIAGNOSTICS_SCHEMA, _handle_get_diagnostics),
)


def async_register_services(hass: HomeAssistant) -> None:
    """Registriert alle OCPP-Services genau einmal.

    Unabhängig von der Anzahl der Config Entries (Services sind Domain-,
    nicht Entry-gebunden, siehe interop-contract.md "Service-Domain-Konvention").
    """
    if hass.services.has_service(DOMAIN, SERVICE_SET_POWER_LIMIT):
        return

    for service, schema, handler in _SERVICES:
        # functools.partial statt lambda: HA erkennt den Service-Handler nur dann
        # korrekt als Coroutine-Funktion (und awaitet ihn selbst, statt eine
        # nie awaitete Coroutine zurückzubekommen), wenn `asyncio.iscoroutinefunction`
        # darauf zutrifft -- eine Lambda, die intern eine Coroutine zurückgibt,
        # ist selbst KEINE Coroutine-Funktion; ein `partial` einer `async def`
        # bleibt hingegen als solche erkennbar.
        hass.services.async_register(
            DOMAIN,
            service,
            functools.partial(handler, hass),
            schema=schema,
            supports_response=SupportsResponse.ONLY,
        )
