"""Transaktions-ID der letzten (aktiven oder beendeten) Session (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData

from ._base import _OcppConnectorSensorBase


class OcppLastTransactionIdSensor(_OcppConnectorSensorBase):
    """Transaktions-ID der letzten Session auf diesem Connector, aktiv oder bereits beendet."""

    _attr_translation_key = "last_transaction_id"

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "last_transaction_id")

    @property
    def native_value(self) -> int | None:
        """Return the last transaction's id, or `None` if this connector never had one."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        return transaction.transaction_id if transaction is not None else None
