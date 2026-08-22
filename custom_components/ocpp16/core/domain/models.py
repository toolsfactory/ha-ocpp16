"""Shared read-side data model.

``ChargePointRegistry``, ``QueryService`` and their dataclasses are copied
verbatim from ``docs/architecture/interfaces.md`` (verbindlich seit
ADR-0003, seit der Ergänzung 2026-08-15 inklusive ``get_connectors``,
``get_meter_samples`` and ``MeterSample``) — do not change field
names/types here without an ADR update there first.

``MeterSample`` and the ``get_connectors``/``get_meter_samples`` methods on
``QueryService`` were originally an OCPP-internal addition *beyond* the
then-frozen ADR-0003 contract, closing the gap ADR-0003 itself flagged as
open (Measurand-resolved live readings, REQ-0008 AC2, REQ-0011 AC1
"aktuelle Messwerte"). Since the 2026-08-15 addendum to ADR-0003, both are
formal, verbindlich documented members of the ``QueryService`` ``Protocol``
below — the console (REQ-0032/REQ-0033) and the future HA layer
(REQ-0017/REQ-0018) share the same contract.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol


class ConnectionStatus(StrEnum):
    """WebSocket-Verbindungsstatus eines Charge Points."""

    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True)
class ChargePointSnapshot:
    """Lesbarer Snapshot des Registry-Eintrags eines Charge Points."""

    charge_point_id: str
    connection_status: ConnectionStatus
    last_boot_at: datetime | None
    last_heartbeat_at: datetime | None
    vendor: str | None
    model: str | None
    firmware_version: str | None
    reconnect_count: int


class ChargePointRegistry(Protocol):
    """Read-only Zugriff auf bekannte Charge Points."""

    def get(self, charge_point_id: str) -> ChargePointSnapshot | None:
        """Return the snapshot for `charge_point_id`, or None if unknown."""
        ...

    def list_all(self) -> Sequence[ChargePointSnapshot]:
        """Return snapshots for every known charge point."""
        ...


@dataclass(frozen=True)
class ConnectorSnapshot:
    """Lesbarer Snapshot des Zustands eines einzelnen Connectors."""

    charge_point_id: str
    connector_id: int
    status: str  # OCPP-1.6-Connector-Status, siehe REQ-0004
    error_code: str | None


@dataclass(frozen=True)
class TransactionSnapshot:
    """Lesbarer Snapshot einer laufenden oder abgeschlossenen Transaktion."""

    transaction_id: int
    charge_point_id: str
    connector_id: int
    id_tag: str
    started_at: datetime
    stopped_at: datetime | None
    meter_start_wh: int
    meter_stop_wh: int | None
    stop_reason: str | None


@dataclass(frozen=True)
class StateChangeEvent:
    """Change-Notification, die über den `EventBus` publiziert wird."""

    charge_point_id: str
    connector_id: int | None
    transaction_id: int | None


class StateChangeListener(Protocol):
    """Callback-Signatur für `EventBus.subscribe`."""

    def __call__(self, event: StateChangeEvent) -> None:
        """Handle a published `StateChangeEvent`."""
        ...


class QueryService(Protocol):
    """Read-only Zugriff auf Charge-Point-, Connector- und Transaktionsdaten."""

    def get_charge_points(self) -> Sequence[ChargePointSnapshot]:
        """Return snapshots for every known charge point."""
        ...

    def get_connector(self, charge_point_id: str, connector_id: int) -> ConnectorSnapshot | None:
        """Return the connector's snapshot, or None if unknown."""
        ...

    def get_connectors(self, charge_point_id: str) -> Sequence[ConnectorSnapshot]:
        """Alle Connectors eines Charge Points (REQ-0032 AC1, REQ-0017 AC2).

        Verbindlich seit der Ergänzung 2026-08-15 zu ADR-0003.
        """
        ...

    def get_transaction(self, transaction_id: int) -> TransactionSnapshot | None:
        """Return the transaction's snapshot, or None if unknown."""
        ...

    def get_active_transactions(self, charge_point_id: str | None = None) -> Sequence[TransactionSnapshot]:
        """Return active transactions, optionally scoped to one charge point."""
        ...

    def get_last_transaction(self, charge_point_id: str, connector_id: int) -> TransactionSnapshot | None:
        """Die zuletzt (aktive oder beendete) Transaktion eines Connectors, oder ``None`` falls nie eine stattfand.

        Additiv wie ``get_connectors``/``get_meter_samples`` unten -- REQ-0011/REQ-0032 verlangten ursprünglich nur
        ``get_active_transactions``; für Sitzungsdiagnostik (Transaktions-ID/Dauer/Energie/Stop-Grund auch nach
        Sessionende, seit 2026-08-21) reicht das nicht. Wie bei ``INTEROP_CONTRACT.md``'s eigener Provenance-Notiz
        gibt es keine lokale ``interfaces.md``/ADR-0003-Quelle in diesem Repository, die diese Erweiterung formal
        fortschreiben könnte -- dieser Docstring ist der Verweis darauf, nicht ein Ersatz dafür.
        """
        ...

    def get_meter_samples(
        self,
        *,
        charge_point_id: str,
        connector_id: int | None = None,
        transaction_id: int | None = None,
    ) -> Sequence[MeterSample]:
        """Measurand-aufgelöste Messwerte, gefiltert nach Connector oder Transaktion.

        REQ-0011 AC1, REQ-0008 AC2, REQ-0018 AC1. ``transaction_id`` hat
        Vorrang vor ``connector_id``; fehlt beides, liefert die Methode eine
        leere Sequenz statt einer Exception. Verbindlich seit der Ergänzung
        2026-08-15 zu ADR-0003.
        """
        ...

    def subscribe(self, listener: StateChangeListener) -> Callable[[], None]:
        """Registriert einen Listener, gibt eine Unsubscribe-Funktion zurück."""
        ...


@dataclass(frozen=True)
class MeterSample:
    """Most recent Measurand-resolved reading (REQ-0008 AC2).

    See module docstring: verbindlicher Bestandteil des ``QueryService``
    ``Protocol`` seit der Ergänzung 2026-08-15 zu ADR-0003.
    """

    measurand: str
    value: str
    unit: str | None
    context: str | None
    phase: str | None
    recorded_at: datetime
