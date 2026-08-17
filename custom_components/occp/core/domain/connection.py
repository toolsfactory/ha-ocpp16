"""Struktureller Vertrag, den eine aktive OCPP-1.6-Verbindung erfüllen muss,
damit ``registry``/``commands`` sie ansteuern können, ohne von der
konkreten ``occp.ocpp16.handlers.ChargePointHandler``-Klasse zu importieren
(vermeidet einen Zyklus domain <-> ocpp16 und hält die Kapselung aus
ADR-0001: die Domänenschicht kennt keine ``ocpp.*``-Typen).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, Sequence

if TYPE_CHECKING:
    # Nur für Typprüfung: würde zur Laufzeit einen Zyklus mit
    # occp.domain.commands (importiert seinerseits ChargePointConnection)
    # erzeugen, siehe ADR-0006.
    from custom_components.occp.core.domain.commands import CompositeScheduleResult


class ChargePointConnection(Protocol):
    """Von ``ChargePointHandler`` (occp.ocpp16.handlers) strukturell erfüllt."""

    charge_point_id: str

    async def close_connection(self, *, reason: str = "") -> None: ...

    async def remote_start_transaction(
        self, connector_id: int | None, id_tag: str
    ) -> str:
        """Gibt den ``RemoteStartStopStatus``-Wert als String zurück."""
        ...

    async def remote_stop_transaction(self, transaction_id: int) -> str: ...

    async def reset(self, reset_type: str) -> str: ...

    async def unlock_connector(self, connector_id: int) -> str: ...

    async def get_configuration(
        self, keys: Sequence[str] | None
    ) -> tuple[list[dict], list[str]]:
        """Gibt (configuration_key-Einträge, unknown_key) zurück."""
        ...

    async def change_configuration(self, key: str, value: str) -> str: ...

    async def set_charging_profile(
        self,
        connector_id: int,
        charging_profile_id: int,
        limit_watts: float,
        number_phases: int | None = None,
    ) -> str:
        """Gibt den ``ChargingProfileStatus``-Wert als String zurück."""
        ...

    async def clear_charging_profile(self, connector_id: int) -> str:
        """Gibt den ``ClearChargingProfileStatus``-Wert als String zurück."""
        ...

    async def get_composite_schedule(
        self, connector_id: int, duration_seconds: int
    ) -> "CompositeScheduleResult":
        """Fragt den effektiv geltenden Leistungsverlauf ab (chargingRateUnit
        fest 'W', REQ-0023 v1) und liefert bereits den fertig abgebildeten
        ``CompositeScheduleResult`` (ADR-0006)."""
        ...

    async def change_availability(self, connector_id: int, availability_type: str) -> str:
        """Gibt den ``AvailabilityStatus``-Wert als String zurück (ADR-0009)."""
        ...
