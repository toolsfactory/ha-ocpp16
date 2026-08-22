"""Struktureller Vertrag, den eine aktive OCPP-1.6-Verbindung erfüllen muss.

Damit ``registry``/``commands`` sie ansteuern können, ohne von der
konkreten ``core.ocpp16.handlers.ChargePointHandler``-Klasse zu importieren
(vermeidet einen Zyklus domain <-> ocpp16 und hält die Kapselung aus
ADR-0001: die Domänenschicht kennt keine ``ocpp.*``-Typen).
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    # Nur für Typprüfung: würde zur Laufzeit einen Zyklus mit
    # core.domain.commands (importiert seinerseits ChargePointConnection)
    # erzeugen, siehe ADR-0006.
    from custom_components.ocpp16.core.domain.commands import CompositeScheduleResult


class ChargePointConnection(Protocol):
    """Von ``ChargePointHandler`` (core.ocpp16.handlers) strukturell erfüllt."""

    @property
    def charge_point_id(self) -> str:
        """Return the charge point's identity."""
        ...

    async def close_connection(self, *, reason: str = "") -> None:
        """Close the connection."""
        ...

    async def remote_start_transaction(self, connector_id: int | None, id_tag: str) -> str:
        """Gibt den ``RemoteStartStopStatus``-Wert als String zurück."""
        ...

    async def remote_stop_transaction(self, transaction_id: int) -> str:
        """Return the RemoteStopTransaction status as a string."""
        ...

    async def reset(self, reset_type: str) -> str:
        """Return the Reset status as a string."""
        ...

    async def unlock_connector(self, connector_id: int) -> str:
        """Return the UnlockConnector status as a string."""
        ...

    async def get_configuration(self, keys: Sequence[str] | None) -> tuple[list[dict], list[str]]:
        """Gibt (configuration_key-Einträge, unknown_key) zurück."""
        ...

    async def change_configuration(self, key: str, value: str) -> str:
        """Return the ChangeConfiguration status as a string."""
        ...

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

    async def get_composite_schedule(self, connector_id: int, duration_seconds: int) -> CompositeScheduleResult:
        """Fragt den effektiv geltenden Leistungsverlauf ab (chargingRateUnit fest 'W', REQ-0023 v1).

        Liefert bereits den fertig abgebildeten ``CompositeScheduleResult`` (ADR-0006).
        """
        ...

    async def change_availability(self, connector_id: int, availability_type: str) -> str:
        """Gibt den ``AvailabilityStatus``-Wert als String zurück (ADR-0009)."""
        ...

    async def trigger_message(self, requested_message: str, connector_id: int | None) -> str:
        """Gibt den ``TriggerMessageStatus``-Wert als String zurück."""
        ...

    async def get_diagnostics(
        self,
        location: str,
        *,
        retries: int | None,
        retry_interval: int | None,
        start_time: str | None,
        stop_time: str | None,
    ) -> str | None:
        """Gibt den vom Charge Point gemeldeten Dateinamen zurück, oder ``None`` (optional laut OCPP 1.6)."""
        ...
