"""Stop-Grund der letzten beendeten Session (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData

from ._base import _OcppConnectorSensorBase


class OcppLastStopReasonSensor(_OcppConnectorSensorBase):
    """Von OCPP gemeldeter Stop-Grund der letzten Session.

    Roher OCPP-Wert ohne ``SensorDeviceClass.ENUM``-Einschränkung -- absichtlich defensiv wie
    ``charge_point_state``'s ``raw_ocpp_status``-Attribut, da nicht jedes Ladegerät exakt
    spezifikationskonforme ``Reason``-Werte meldet.
    """

    _attr_translation_key = "last_stop_reason"

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "last_stop_reason")

    @property
    def native_value(self) -> str | None:
        """Return the last session's stop reason, or `None` if it's still active or never stopped."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        return transaction.stop_reason if transaction is not None else None
