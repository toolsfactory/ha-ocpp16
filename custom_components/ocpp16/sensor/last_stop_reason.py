"""Stop-Grund der letzten beendeten Session (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.components.sensor import RestoreSensor

from ._base import _OcppConnectorSensorBase


class Ocpp16LastStopReasonSensor(_OcppConnectorSensorBase, RestoreSensor):
    """Von OCPP gemeldeter Stop-Grund der letzten Session.

    Roher OCPP-Wert ohne ``SensorDeviceClass.ENUM``-Einschränkung -- absichtlich defensiv wie
    ``charge_point_state``'s ``raw_ocpp_status``-Attribut, da nicht jedes Ladegerät exakt
    spezifikationskonforme ``Reason``-Werte meldet.

    Über einen HA-Neustart hinweg wird der zuletzt bekannte Wert per ``RestoreSensor``
    wiederhergestellt, bis diese Prozesslaufzeit selbst eine Transaktion auf diesem Connector sieht.
    """

    _attr_translation_key = "last_stop_reason"

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "last_stop_reason")
        self._restored_value: str | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known stop reason across a HA restart, if one was ever recorded."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and last_data.native_value is not None:
            self._restored_value = str(last_data.native_value)

    @property
    def native_value(self) -> str | None:
        """Return the last session's stop reason, or the restored value if none happened yet."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        if transaction is not None:
            return transaction.stop_reason
        return self._restored_value
