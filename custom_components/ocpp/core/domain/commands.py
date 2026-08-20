"""``CommandService``: Central-System-initiierte Aufrufe an einen Charge Point.

REQ-0009, REQ-0010, REQ-0012, REQ-0013, REQ-0014. Kein formales ADR-0003-Pendant existiert für diese Schnittstelle (siehe
architecture.md: "Command-... Services sind grob skizziert, nicht final
spezifiziert") — sie wird hier trotzdem als eine einzige, saubere
Protocol/Service-Grenze umgesetzt, weil sowohl die Konsole (ADR-0002) als
auch der künftige HA-Layer (Stufe 4, REQ-0020) sie modulübergreifend
brauchen. Empfehlung an den architect-Agenten: vor Stufe 4 in
``interfaces.md`` nachziehen (siehe Abschlussbericht).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from custom_components.ocpp.core.domain.connection import ChargePointConnection
from custom_components.ocpp.core.domain.registry import ChargePointRegistryStore
from custom_components.ocpp.core.domain.transactions import TransactionManager


class CommandError(Exception):
    """Basisklasse für alle vom CommandService abgelehnten Aufrufe."""


class ChargePointNotConnectedError(CommandError):
    """Der Ziel-Charge-Point hat keine aktive Verbindung."""


class TransactionNotActiveError(CommandError):
    """Die Ziel-Transaktion läuft nicht (mehr)."""


class ChargePointCallRejectedError(CommandError):
    """Der Charge Point hat den Aufruf mit einem OCPP-``CallError`` statt einer regulären Antwort quittiert."""


class InvalidConnectorError(CommandError):
    """connectorId < 1.

    REQ-0023 v1: kein charge-point-weiter Geltungsbereich über connectorId 0.
    Seit ADR-0006.
    """


class InvalidNumberPhasesError(CommandError):
    """numberPhases außerhalb 1-3 (OCPP 1.6 chargingSchedulePeriod).

    Seit ADR-0006 (Ergänzung 2026-08-15b).
    """


@dataclass(frozen=True)
class RemoteStartResult:
    """Ergebnis von `CommandService.remote_start_transaction`."""

    accepted: bool


@dataclass(frozen=True)
class RemoteStopResult:
    """Ergebnis von `CommandService.remote_stop_transaction`."""

    accepted: bool


@dataclass(frozen=True)
class ResetResult:
    """Ergebnis von `CommandService.reset`."""

    accepted: bool


@dataclass(frozen=True)
class UnlockResult:
    """Ergebnis von `CommandService.unlock_connector`."""

    status: str  # "Unlocked" | "UnlockFailed" | "NotSupported"


@dataclass(frozen=True)
class ConfigurationEntry:
    """Ein einzelner von GetConfiguration.conf gemeldeter Konfigurationswert."""

    key: str
    value: str | None
    readonly: bool


@dataclass(frozen=True)
class GetConfigurationResult:
    """Ergebnis von `CommandService.get_configuration`."""

    entries: Sequence[ConfigurationEntry]
    unknown_keys: Sequence[str]


@dataclass(frozen=True)
class ChangeConfigurationResult:
    """Ergebnis von `CommandService.change_configuration`."""

    status: str  # "Accepted" | "Rejected" | "RebootRequired" | "NotSupported"


@dataclass(frozen=True)
class SetChargingProfileResult:
    """Ergebnis von `CommandService.set_charging_profile`. Seit ADR-0006 (REQ-0023, REQ-0033)."""

    status: str  # ChargingProfileStatus: "Accepted" | "Rejected" | "NotSupported"
    charging_profile_id: int  # deterministisch == connector_id, siehe ADR-0006


@dataclass(frozen=True)
class ClearChargingProfileResult:
    """Ergebnis von `CommandService.clear_charging_profile`. Seit ADR-0006 (REQ-0023, REQ-0033).

    Achtung: eigenes, kleineres Statuswertespektrum als SetChargingProfileResult
    (ClearChargingProfileStatus laut OCPP 1.6 — kein "Rejected"/"NotSupported").
    """

    status: str  # ClearChargingProfileStatus: "Accepted" | "Unknown"


@dataclass(frozen=True)
class ChargingSchedulePeriodInfo:
    """Ein Eintrag im vom Charge Point gemeldeten Leistungsverlauf.

    Seit ADR-0006 (Ergänzung 2026-08-15, REQ-0023 AC3) -- rein lesend, kein
    neues, von OCPP schreibbares Zeitplan-Konzept.
    """

    start_offset_seconds: int  # startPeriod, relativ zu schedule_start
    limit_watts: float


@dataclass(frozen=True)
class CompositeScheduleResult:
    """Ergebnis von `CommandService.get_composite_schedule`.

    Seit ADR-0006 (Ergänzung 2026-08-15, REQ-0023 AC3). ``periods`` kann
    mehrere Einträge enthalten (Charge Point meldet ggf. einen mehrstufigen
    effektiven Verlauf) -- das ist keine neue Zeitplan-Flexibilität von OCPP
    selbst, siehe ADR-0006.
    """

    status: str  # CompositeScheduleStatus: "Accepted" | "Rejected"
    connector_id: int | None = None
    schedule_start: datetime | None = None
    duration_seconds: int | None = None
    charging_rate_unit: str | None = None  # vom Charge Point gemeldet, siehe ADR-0006
    periods: Sequence[ChargingSchedulePeriodInfo] = ()


@dataclass(frozen=True)
class ChangeAvailabilityResult:
    """Seit ADR-0009 (REQ-0021)."""

    status: str  # AvailabilityStatus: "Accepted" | "Rejected" | "Scheduled"


@dataclass(frozen=True)
class TriggerMessageResult:
    """Ergebnis von `CommandService.trigger_message`."""

    status: str  # TriggerMessageStatus: "Accepted" | "Rejected" | "NotImplemented"


class CommandService:
    """Central-System-initiierte Aufrufe an einen verbundenen Charge Point."""

    def __init__(
        self,
        *,
        registry: ChargePointRegistryStore,
        transactions: TransactionManager,
    ) -> None:
        """Initialize the service with the registry and transaction manager it calls into."""
        self._registry = registry
        self._transactions = transactions

    async def remote_start_transaction(
        self, charge_point_id: str, connector_id: int | None, id_tag: str
    ) -> RemoteStartResult:
        """Send RemoteStartTransaction to the charge point."""
        connection = self._require_connection(charge_point_id)
        status = await connection.remote_start_transaction(connector_id, id_tag)
        return RemoteStartResult(accepted=status == "Accepted")

    async def remote_stop_transaction(self, transaction_id: int) -> RemoteStopResult:
        """Send RemoteStopTransaction for an active transaction."""
        transaction = self._transactions.get(transaction_id)
        if transaction is None or transaction.stopped_at is not None:
            raise TransactionNotActiveError(f"Transaktion {transaction_id} läuft nicht (mehr).")
        connection = self._require_connection(transaction.charge_point_id)
        status = await connection.remote_stop_transaction(transaction_id)
        return RemoteStopResult(accepted=status == "Accepted")

    async def reset(self, charge_point_id: str, reset_type: str) -> ResetResult:
        """Send Reset to the charge point."""
        connection = self._require_connection(charge_point_id)
        status = await connection.reset(reset_type)
        return ResetResult(accepted=status == "Accepted")

    async def unlock_connector(self, charge_point_id: str, connector_id: int) -> UnlockResult:
        """Send UnlockConnector for the given connector."""
        connection = self._require_connection(charge_point_id)
        status = await connection.unlock_connector(connector_id)
        return UnlockResult(status=status)

    async def get_configuration(
        self, charge_point_id: str, keys: Sequence[str] | None = None
    ) -> GetConfigurationResult:
        """Send GetConfiguration, optionally scoped to `keys`."""
        connection = self._require_connection(charge_point_id)
        raw_entries, unknown_keys = await connection.get_configuration(keys)
        entries = [
            ConfigurationEntry(
                key=entry["key"],
                value=entry.get("value"),
                readonly=bool(entry.get("readonly", False)),
            )
            for entry in raw_entries
        ]
        return GetConfigurationResult(entries=entries, unknown_keys=list(unknown_keys))

    async def change_configuration(self, charge_point_id: str, key: str, value: str) -> ChangeConfigurationResult:
        """Send ChangeConfiguration for a single key."""
        connection = self._require_connection(charge_point_id)
        status = await connection.change_configuration(key, value)
        return ChangeConfigurationResult(status=status)

    async def set_charging_profile(
        self,
        charge_point_id: str,
        connector_id: int,
        limit_watts: float,
        number_phases: int | None = None,
    ) -> SetChargingProfileResult:
        """Send SetChargingProfile with a TxDefaultProfile power limit for the connector."""
        self._require_valid_connector(connector_id)
        self._require_valid_number_phases(number_phases)
        connection = self._require_connection(charge_point_id)
        status = await connection.set_charging_profile(connector_id, connector_id, limit_watts, number_phases)
        return SetChargingProfileResult(status=status, charging_profile_id=connector_id)

    async def clear_charging_profile(self, charge_point_id: str, connector_id: int) -> ClearChargingProfileResult:
        """Send ClearChargingProfile for the connector's TxDefaultProfile."""
        self._require_valid_connector(connector_id)
        connection = self._require_connection(charge_point_id)
        status = await connection.clear_charging_profile(connector_id)
        return ClearChargingProfileResult(status=status)

    async def get_composite_schedule(
        self, charge_point_id: str, connector_id: int, duration_seconds: int = 3600
    ) -> CompositeScheduleResult:
        """Send GetCompositeSchedule for the connector."""
        self._require_valid_connector(connector_id)
        connection = self._require_connection(charge_point_id)
        return await connection.get_composite_schedule(connector_id, duration_seconds)

    async def change_availability(
        self, charge_point_id: str, connector_id: int, availability_type: str
    ) -> ChangeAvailabilityResult:
        """Send ChangeAvailability for the connector."""
        self._require_valid_connector(connector_id)
        connection = self._require_connection(charge_point_id)
        status = await connection.change_availability(connector_id, availability_type)
        return ChangeAvailabilityResult(status=status)

    async def trigger_message(
        self, charge_point_id: str, requested_message: str, connector_id: int | None = None
    ) -> TriggerMessageResult:
        """Send TriggerMessage, optionally scoped to a connector."""
        if connector_id is not None:
            self._require_valid_connector(connector_id)
        connection = self._require_connection(charge_point_id)
        status = await connection.trigger_message(requested_message, connector_id)
        return TriggerMessageResult(status=status)

    def _require_valid_connector(self, connector_id: int) -> None:
        if connector_id < 1:
            raise InvalidConnectorError(
                f"connectorId {connector_id} ist ungültig (REQ-0023: kein "
                "charge-point-weiter Geltungsbereich über connectorId 0)."
            )

    def _require_valid_number_phases(self, number_phases: int | None) -> None:
        if number_phases is not None and number_phases not in (1, 2, 3):
            raise InvalidNumberPhasesError(f"numberPhases {number_phases} ist ungültig (OCPP 1.6: Wertebereich 1-3).")

    def _require_connection(self, charge_point_id: str) -> ChargePointConnection:
        connection = self._registry.get_active_connection(charge_point_id)
        if connection is None:
            raise ChargePointNotConnectedError(f"Charge Point '{charge_point_id}' ist nicht verbunden.")
        return connection
