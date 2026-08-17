"""Adapter-Modul für den Interop-Vertrag (REQ-0035, ADR-0010).

Bündelt die Abbildung der Interop-Vertrag-Fähigkeiten 1, 3, 4, 5, 7 (Werte)
und 8 auf ``CommandService``/``QueryService``/``AuthorizationProvider`` an
einer Stelle -- ``sensor.py``/``switch.py``/``services.py`` rufen diese
Funktionen auf, statt Vertragsdetails selbst zu kennen (ADR-0010,
"Adapter-Modul").

Fähigkeit 2 (REQ-0019) und Fähigkeit 6 (REQ-0021) sind bewusst **nicht**
hier, da sie durch eigene REQs abgedeckt sind (siehe ADR-0010 Non-Goals-
Abgrenzung in REQ-0035).
"""

from custom_components.occp.core.domain.authorization import AuthorizationProvider, IdTagStatus
from custom_components.occp.core.domain.commands import CommandService
from custom_components.occp.core.domain.models import QueryService

from .const import MEASURAND_POWER_ACTIVE_IMPORT

# -- Fähigkeit 1 --------------------------------------------------------


def get_current_power_w(query_service: QueryService, charge_point_id: str, connector_id: int) -> float | None:
    """Aktuelle Ladeleistung (ADR-0010, Fähigkeit 1).

    ``None`` -> Entity ``unavailable`` (REQ-0035 AC1).
    """
    samples = query_service.get_meter_samples(charge_point_id=charge_point_id, connector_id=connector_id)
    matching = [s for s in samples if s.measurand == MEASURAND_POWER_ACTIVE_IMPORT]
    if not matching:
        return None
    latest = max(matching, key=lambda s: s.recorded_at)
    return float(latest.value)


# -- Fähigkeit 3/4 --------------------------------------------------------

_SET_LIMIT_STATUS_MAP = {
    "Accepted": "accepted",
    "Rejected": "rejected",
    "NotSupported": "not_supported",
}

_CLEAR_LIMIT_STATUS_MAP = {
    "Accepted": "accepted",
    "Unknown": "unknown",
}


async def set_power_limit(
    command_service: CommandService,
    charge_point_id: str,
    connector_id: int,
    limit_w: float,
    phases: int | None,
) -> dict:
    """Setzt ein ``TxDefaultProfile`` per ``SetChargingProfile`` (ADR-0010, Fähigkeit 3).

    Bildet den Status auf das Vertragsschema ab. Wirft die unveränderten
    ``CommandError``-Subtypen des Kerns weiter -- die Behandlung "Ziel
    unbekannt/nicht verbunden" obliegt dem Aufrufer (``services.py``, ADR-0010).
    """
    result = await command_service.set_charging_profile(charge_point_id, connector_id, limit_w, number_phases=phases)
    return {"status": _SET_LIMIT_STATUS_MAP.get(result.status, result.status)}


async def clear_power_limit(command_service: CommandService, charge_point_id: str, connector_id: int) -> dict:
    """Fähigkeit 4 (ADR-0010)."""
    result = await command_service.clear_charging_profile(charge_point_id, connector_id)
    return {"status": _CLEAR_LIMIT_STATUS_MAP.get(result.status, result.status)}


# -- Fähigkeit 5 --------------------------------------------------------


async def get_effective_power_limit_w(
    command_service: CommandService, charge_point_id: str, connector_id: int
) -> float | None:
    """Fähigkeit 5 (ADR-0010).

    ``None`` -> Entity-Zustand ``unknown``, NICHT ``0`` (REQ-0035 AC4).
    """
    result = await command_service.get_composite_schedule(charge_point_id, connector_id)
    if result.status != "Accepted" or not result.periods:
        return None
    return result.periods[0].limit_watts


# -- Fähigkeit 8 --------------------------------------------------------

_ID_TAG_STATUS_MAP: dict[IdTagStatus, str] = {
    IdTagStatus.ACCEPTED: "accepted",
    IdTagStatus.BLOCKED: "blocked",
    IdTagStatus.EXPIRED: "expired",
    IdTagStatus.INVALID: "invalid",
}


def authorize_id_token(provider: AuthorizationProvider, id_token: str) -> dict:
    """Bildet ``IdTagStatus`` auf das Vertragsschema ab (ADR-0010, Fähigkeit 8).

    ``status: "unknown"`` liefert OCCP als Anbieter nie, siehe ADR-0010.
    """
    decision = provider.authorize(id_token)
    status = _ID_TAG_STATUS_MAP[decision.status]
    return {"authorized": status == "accepted", "status": status}
