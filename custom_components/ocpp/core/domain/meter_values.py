"""Messwerterfassung (REQ-0008).

Speichert je Connector bzw. Transaktion für jedes (Measurand, Phase)-Paar den
zuletzt empfangenen Wert -- ein phasenloser Gesamtwert und L1/L2/L3-Werte
desselben Measurands koexistieren, statt sich gegenseitig zu überschreiben.
``MeterValues`` können außerhalb einer laufenden Transaktion eintreffen
(REQ-0008 AC3) — diese werden ausschließlich dem Connector zugeordnet.
"""

from collections.abc import Sequence

from custom_components.ocpp.core.domain.models import MeterSample


class MeterValueStore:
    """Speichert je Connector bzw. Transaktion den zuletzt empfangenen Messwert je (Measurand, Phase) (REQ-0008)."""

    def __init__(self) -> None:
        """Initialize with no recorded samples."""
        self._by_connector: dict[tuple[str, int], dict[tuple[str, str | None], MeterSample]] = {}
        self._by_transaction: dict[int, dict[tuple[str, str | None], MeterSample]] = {}

    def record(
        self,
        *,
        charge_point_id: str,
        connector_id: int,
        transaction_id: int | None,
        samples: Sequence[MeterSample],
    ) -> None:
        """Record the latest sample per (measurand, phase) for the connector and, if active, the transaction."""
        connector_key = (charge_point_id, connector_id)
        connector_bucket = self._by_connector.setdefault(connector_key, {})
        transaction_bucket = self._by_transaction.setdefault(transaction_id, {}) if transaction_id is not None else None
        for sample in samples:
            sample_key = (sample.measurand, sample.phase)
            connector_bucket[sample_key] = sample
            if transaction_bucket is not None:
                transaction_bucket[sample_key] = sample

    def get_for_connector(self, charge_point_id: str, connector_id: int) -> Sequence[MeterSample]:
        """Return the connector's most recent sample per measurand."""
        return list(self._by_connector.get((charge_point_id, connector_id), {}).values())

    def get_for_transaction(self, transaction_id: int) -> Sequence[MeterSample]:
        """Return the transaction's most recent sample per measurand."""
        return list(self._by_transaction.get(transaction_id, {}).values())
