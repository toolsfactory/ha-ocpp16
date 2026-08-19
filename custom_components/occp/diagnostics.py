"""Diagnostics für einen Config Entry (Quality-Scale-Regel ``diagnostics``)."""

from typing import Any

from custom_components.occp.const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, CONF_HOST
from custom_components.occp.runtime import OccpConfigEntry
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

# Host (Netzwerkadresse) und der Pfad zur Autorisierungsdatei können Systemdetails
# preisgeben; das Default-idTag ist ein echtes Credential -- alle drei werden
# geschwärzt. Port ist keine identifizierende Information.
_TO_REDACT = {CONF_HOST, CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: OccpConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Absichtlich keine vollständigen OCPP-Frames und keine rohen idTag-Werte aus
    der Autorisierungsliste -- nur eine Zusammenfassung dessen, was OCCP aktuell
    über jeden verbundenen Charge Point weiß.
    """
    entry_data = entry.runtime_data
    query_service = entry_data.app.query_service

    charge_points = []
    for snapshot in query_service.get_charge_points():
        connectors = query_service.get_connectors(snapshot.charge_point_id)
        charge_points.append(
            {
                # Bewusst nicht geschwärzt -- siehe DECISIONS.md "Accepted risk: charge_point_id
                # is not redacted in diagnostics" (bereits als Gerätename überall in der UI sichtbar).
                "charge_point_id": snapshot.charge_point_id,
                "connection_status": snapshot.connection_status,
                "vendor": snapshot.vendor,
                "model": snapshot.model,
                "firmware_version": snapshot.firmware_version,
                "connectors": [
                    {
                        "connector_id": connector.connector_id,
                        "status": connector.status,
                        "error_code": connector.error_code,
                    }
                    for connector in connectors
                ],
            }
        )

    return {
        "entry_data": async_redact_data(dict(entry.data), _TO_REDACT),
        "entry_options": async_redact_data(dict(entry.options), _TO_REDACT),
        "default_id_tag_configured": bool(entry_data.default_id_tag),
        "charge_point_count": len(charge_points),
        "charge_points": charge_points,
    }
