"""Gemeinsame Device-/Entry-Resolver für alle OCPP-Service-Handler.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Handler aus den Geschwistermodulen für ``_SERVICES``, ein Import in
Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.entity_utils.device import parse_charge_point_identifier, parse_connector_identifier
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr


def _get_device_entry(hass: HomeAssistant, call: ServiceCall) -> dr.DeviceEntry:
    device_id: str = call.data[ATTR_DEVICE_ID]
    device_entry = dr.async_get(hass).async_get(device_id)
    if device_entry is None:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_not_found",
            translation_placeholders={"device_id": device_id},
        )
    return device_entry


def _entry_data_for_device(hass: HomeAssistant, device_entry: dr.DeviceEntry) -> OcppEntryData:
    """Resolve the `OcppEntryData` of the config entry that owns `device_entry`.

    Ein Gerät gehört seit HA 2026.8 genau einem Config Entry
    (``DeviceEntry.config_entry_id``) -- eine globale Suche über alle
    geladenen Entries nach einer passenden ``charge_point_id`` würde bei
    zwei Instanzen mit zufällig gleicher ``chargePointId`` die falsche
    treffen können, siehe ``_find_entry_data`` unten.
    """
    entry_id = device_entry.config_entry_id
    entry = hass.config_entries.async_get_entry(entry_id) if entry_id else None
    if entry is None or entry.state is not entry.state.LOADED:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="device_entry_not_loaded",
            translation_placeholders={"device_id": device_entry.id},
        )
    return entry.runtime_data


def _resolve_single_connector_device(hass: HomeAssistant, call: ServiceCall) -> tuple[OcppEntryData, str, int]:
    """Resolve `call.data[ATTR_DEVICE_ID]` to its owning entry, charge_point_id, and connector_id."""
    device_entry = _get_device_entry(hass, call)

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        parsed = parse_connector_identifier(identifier)
        if parsed is not None:
            charge_point_id, connector_id = parsed
            return _entry_data_for_device(hass, device_entry), charge_point_id, connector_id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_connector",
        translation_placeholders={"device_id": device_entry.id},
    )


def _resolve_charge_point_device(hass: HomeAssistant, call: ServiceCall) -> tuple[OcppEntryData, str]:
    """Resolve `call.data[ATTR_DEVICE_ID]` to its owning entry and charge_point_id, rejecting a connector device."""
    device_entry = _get_device_entry(hass, call)

    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if parse_connector_identifier(identifier) is not None:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="device_is_connector",
                translation_placeholders={"device_id": device_entry.id},
            )
        charge_point_id = parse_charge_point_identifier(identifier)
        if charge_point_id is None:
            continue
        return _entry_data_for_device(hass, device_entry), charge_point_id

    raise ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key="device_not_ocpp",
        translation_placeholders={"device_id": device_entry.id},
    )


def _find_entry_data(hass: HomeAssistant, charge_point_id: str) -> OcppEntryData | None:
    """Find the entry owning `charge_point_id` by scanning every loaded OCPP entry.

    Nur für ``authorize_id_token`` -- der einzige Service, der eine
    ``charge_point_id`` statt eines Geräts entgegennimmt und daher keinen
    Device-Registry-Eintrag zum gescopten Auflösen hat. Bei zwei Instanzen
    mit zufällig identischer ``chargePointId`` bleibt das mehrdeutig
    (bekannte Einschränkung, siehe Plan/DECISIONS.md).
    """
    for entry in hass.config_entries.async_loaded_entries(DOMAIN):
        entry_data = entry.runtime_data
        if entry_data.app.registry.get(charge_point_id) is not None:
            return entry_data
    return None
