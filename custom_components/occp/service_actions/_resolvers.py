"""Gemeinsame Device-/Entry-Resolver für alle OCCP-Service-Handler.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Handler aus den Geschwistermodulen für ``_SERVICES``, ein Import in
Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.occp.const import DOMAIN
from custom_components.occp.entity_utils.device import parse_connector_identifier
from custom_components.occp.runtime import OccpEntryData
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr


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


def _resolve_charge_point_device(hass: HomeAssistant, call: ServiceCall) -> str:
    """Resolve `call.data[ATTR_DEVICE_ID]` to a charge_point_id, rejecting a connector device."""
    device_id: str = call.data[ATTR_DEVICE_ID]
    registry = dr.async_get(hass)
    device_entry = registry.async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(f"Unbekanntes Gerät '{device_id}'.")

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if parse_connector_identifier(identifier) is not None:
            raise ServiceValidationError(
                f"Gerät '{device_id}' ist ein Connector -- dieser Service benötigt das Charge-Point-Gerät selbst."
            )
        return identifier

    raise ServiceValidationError(f"Gerät '{device_id}' gehört nicht zu OCCP.")


def _find_entry_data(hass: HomeAssistant, charge_point_id: str) -> OccpEntryData | None:
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entry_data = entry.runtime_data
        if entry_data.app.registry.get(charge_point_id) is not None:
            return entry_data
    return None
