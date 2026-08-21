"""Diagnostics für einen Config Entry (Quality-Scale-Regel ``diagnostics``)."""

from typing import Any

from custom_components.ocpp.const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, CONF_HOST
from custom_components.ocpp.core.domain.models import QueryService
from custom_components.ocpp.runtime import OcppConfigEntry
from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

# Host (Netzwerkadresse) und der Pfad zur Autorisierungsdatei können Systemdetails
# preisgeben; das Default-idTag und ein Transaktions-idTag sind echte Credentials -- alle vier
# werden geschwärzt (async_redact_data schwärzt rekursiv, auch im verschachtelten
# last_transaction-Eintrag unten). Port ist keine identifizierende Information.
_TO_REDACT = {CONF_HOST, CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, "id_tag"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: OcppConfigEntry) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Absichtlich keine vollständigen OCPP-Frames und keine rohen idTag-Werte aus
    der Autorisierungsliste -- nur eine Zusammenfassung dessen, was OCPP aktuell
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
                "reconnect_count": snapshot.reconnect_count,
                "vendor": snapshot.vendor,
                "model": snapshot.model,
                "firmware_version": snapshot.firmware_version,
                "connectors": [
                    {
                        "connector_id": connector.connector_id,
                        "status": connector.status,
                        "error_code": connector.error_code,
                        "last_transaction": _last_transaction_diagnostics(
                            query_service, snapshot.charge_point_id, connector.connector_id
                        ),
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
        "charge_points": async_redact_data(charge_points, _TO_REDACT),
    }


def _last_transaction_diagnostics(
    query_service: QueryService, charge_point_id: str, connector_id: int
) -> dict[str, Any] | None:
    """Summarize the connector's most recent transaction (active or stopped), or `None` if there never was one."""
    transaction = query_service.get_last_transaction(charge_point_id, connector_id)
    if transaction is None:
        return None
    return {
        "transaction_id": transaction.transaction_id,
        "id_tag": transaction.id_tag,
        "started_at": transaction.started_at.isoformat(),
        "stopped_at": transaction.stopped_at.isoformat() if transaction.stopped_at else None,
        "stop_reason": transaction.stop_reason,
    }
