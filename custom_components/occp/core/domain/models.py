"""Shared read-side data model.

``ChargePointRegistry``, ``QueryService`` and their dataclasses are copied
verbatim from ``docs/architecture/interfaces.md`` (verbindlich seit
ADR-0003, seit der Ergänzung 2026-08-15 inklusive ``get_connectors``,
``get_meter_samples`` and ``MeterSample``) — do not change field
names/types here without an ADR update there first.

``MeterSample`` and the ``get_connectors``/``get_meter_samples`` methods on
``QueryService`` were originally an OCCP-internal addition *beyond* the
then-frozen ADR-0003 contract, closing the gap ADR-0003 itself flagged as
open (Measurand-resolved live readings, REQ-0008 AC2, REQ-0011 AC1
"aktuelle Messwerte"). Since the 2026-08-15 addendum to ADR-0003, both are
formal, verbindlich documented members of the ``QueryService`` ``Protocol``
below — the console (REQ-0032/REQ-0033) and the future HA layer
(REQ-0017/REQ-0018) share the same contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Protocol, Sequence


class ConnectionStatus(str, Enum):
    ONLINE = "online"
    OFFLINE = "offline"


@dataclass(frozen=True)
class ChargePointSnapshot:
    charge_point_id: str
    connection_status: ConnectionStatus
    last_boot_at: datetime | None
    vendor: str | None
    model: str | None
    firmware_version: str | None


class ChargePointRegistry(Protocol):
    def get(self, charge_point_id: str) -> ChargePointSnapshot | None: ...
    def list_all(self) -> Sequence[ChargePointSnapshot]: ...


@dataclass(frozen=True)
class ConnectorSnapshot:
    charge_point_id: str
    connector_id: int
    status: str  # OCPP-1.6-Connector-Status, siehe REQ-0004
    error_code: str | None


@dataclass(frozen=True)
class TransactionSnapshot:
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
    charge_point_id: str
    connector_id: int | None
    transaction_id: int | None


class StateChangeListener(Protocol):
    def __call__(self, event: StateChangeEvent) -> None: ...


class QueryService(Protocol):
    def get_charge_points(self) -> Sequence[ChargePointSnapshot]: ...
    def get_connector(
        self, charge_point_id: str, connector_id: int
    ) -> ConnectorSnapshot | None: ...
    def get_connectors(self, charge_point_id: str) -> Sequence[ConnectorSnapshot]:
        """Alle Connectors eines Charge Points (REQ-0032 AC1, REQ-0017 AC2).
        Verbindlich seit der Ergänzung 2026-08-15 zu ADR-0003."""
        ...
    def get_transaction(self, transaction_id: int) -> TransactionSnapshot | None: ...
    def get_active_transactions(
        self, charge_point_id: str | None = None
    ) -> Sequence[TransactionSnapshot]: ...
    def get_meter_samples(
        self,
        *,
        charge_point_id: str,
        connector_id: int | None = None,
        transaction_id: int | None = None,
    ) -> Sequence["MeterSample"]:
        """Measurand-aufgelöste Messwerte, gefiltert nach Connector oder
        Transaktion (REQ-0011 AC1, REQ-0008 AC2, REQ-0018 AC1).
        ``transaction_id`` hat Vorrang vor ``connector_id``; fehlt beides,
        liefert die Methode eine leere Sequenz statt einer Exception.
        Verbindlich seit der Ergänzung 2026-08-15 zu ADR-0003."""
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
