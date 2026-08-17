"""Messwerterfassung (REQ-0008): speichert je Connector bzw. Transaktion für
jeden Measurand-Typ den zuletzt empfangenen Wert.

``MeterValues`` können außerhalb einer laufenden Transaktion eintreffen
(REQ-0008 AC3) — diese werden ausschließlich dem Connector zugeordnet.
"""

from __future__ import annotations

from typing import Sequence

from custom_components.occp.core.domain.models import MeterSample


class MeterValueStore:
    def __init__(self) -> None:
        self._by_connector: dict[tuple[str, int], dict[str, MeterSample]] = {}
        self._by_transaction: dict[int, dict[str, MeterSample]] = {}

    def record(
        self,
        *,
        charge_point_id: str,
        connector_id: int,
        transaction_id: int | None,
        samples: Sequence[MeterSample],
    ) -> None:
        connector_key = (charge_point_id, connector_id)
        connector_bucket = self._by_connector.setdefault(connector_key, {})
        transaction_bucket = (
            self._by_transaction.setdefault(transaction_id, {})
            if transaction_id is not None
            else None
        )
        for sample in samples:
            connector_bucket[sample.measurand] = sample
            if transaction_bucket is not None:
                transaction_bucket[sample.measurand] = sample

    def get_for_connector(
        self, charge_point_id: str, connector_id: int
    ) -> Sequence[MeterSample]:
        return list(self._by_connector.get((charge_point_id, connector_id), {}).values())

    def get_for_transaction(self, transaction_id: int) -> Sequence[MeterSample]:
        return list(self._by_transaction.get(transaction_id, {}).values())
