"""Transaktions-Lebenszyklus (REQ-0006, REQ-0007): Start/Stopp, Historie.

Transaktions-IDs werden zentral hier vergeben (monoton steigend, eindeutig
für die Prozesslaufzeit) — Persistenz über einen Neustart hinaus ist laut
architecture.md explizit Non-Goal für Stufe 3.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
import itertools

from custom_components.occp.core.domain.models import TransactionSnapshot


@dataclass
class _TransactionRecord:
    transaction_id: int
    charge_point_id: str
    connector_id: int
    id_tag: str
    started_at: datetime
    meter_start_wh: int
    stopped_at: datetime | None = None
    meter_stop_wh: int | None = None
    stop_reason: str | None = None

    def to_snapshot(self) -> TransactionSnapshot:
        return TransactionSnapshot(
            transaction_id=self.transaction_id,
            charge_point_id=self.charge_point_id,
            connector_id=self.connector_id,
            id_tag=self.id_tag,
            started_at=self.started_at,
            stopped_at=self.stopped_at,
            meter_start_wh=self.meter_start_wh,
            meter_stop_wh=self.meter_stop_wh,
            stop_reason=self.stop_reason,
        )


class TransactionManager:
    """Vergibt Transaktions-IDs und verwaltet den Transaktions-Lebenszyklus."""

    def __init__(self) -> None:
        """Initialize with no recorded transactions."""
        self._records: dict[int, _TransactionRecord] = {}
        self._active_by_connector: dict[tuple[str, int], int] = {}
        self._id_generator = itertools.count(1)

    def start_transaction(
        self,
        *,
        charge_point_id: str,
        connector_id: int,
        id_tag: str,
        meter_start_wh: int,
        started_at: datetime,
    ) -> TransactionSnapshot:
        """Open a new transaction on the connector and return its snapshot."""
        transaction_id = next(self._id_generator)
        record = _TransactionRecord(
            transaction_id=transaction_id,
            charge_point_id=charge_point_id,
            connector_id=connector_id,
            id_tag=id_tag,
            started_at=started_at,
            meter_start_wh=meter_start_wh,
        )
        self._records[transaction_id] = record
        self._active_by_connector[(charge_point_id, connector_id)] = transaction_id
        return record.to_snapshot()

    def stop_transaction(
        self,
        transaction_id: int,
        *,
        meter_stop_wh: int,
        stopped_at: datetime,
        reason: str | None,
    ) -> TransactionSnapshot | None:
        """Beendet eine Transaktion.

        Gibt ``None`` zurück, wenn ``transaction_id`` unbekannt ist (REQ-0007
        AC3: Aufrufer antwortet trotzdem regulär, protokolliert nur die
        Abweichung).
        """
        record = self._records.get(transaction_id)
        if record is None:
            return None
        record.stopped_at = stopped_at
        record.meter_stop_wh = meter_stop_wh
        record.stop_reason = reason
        active_key = (record.charge_point_id, record.connector_id)
        if self._active_by_connector.get(active_key) == transaction_id:
            del self._active_by_connector[active_key]
        return record.to_snapshot()

    def get(self, transaction_id: int) -> TransactionSnapshot | None:
        """Return the transaction's snapshot, or None if unknown."""
        record = self._records.get(transaction_id)
        return record.to_snapshot() if record is not None else None

    def get_active_transactions(self, charge_point_id: str | None = None) -> Sequence[TransactionSnapshot]:
        """Return active transactions, optionally scoped to one charge point."""
        result = []
        for transaction_id in self._active_by_connector.values():
            record = self._records[transaction_id]
            if charge_point_id is not None and record.charge_point_id != charge_point_id:
                continue
            result.append(record.to_snapshot())
        return result

    def get_active_transaction_id(self, charge_point_id: str, connector_id: int) -> int | None:
        """Return the active transaction id for the connector, if any."""
        return self._active_by_connector.get((charge_point_id, connector_id))

    def is_active(self, transaction_id: int) -> bool:
        """Return whether the transaction exists and has not been stopped."""
        record = self._records.get(transaction_id)
        return record is not None and record.stopped_at is None
