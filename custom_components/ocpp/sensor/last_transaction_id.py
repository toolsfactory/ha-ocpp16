"""Transaktions-ID der letzten (aktiven oder beendeten) Session (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import RestoreSensor

from ._base import _OcppConnectorSensorBase


class OcppLastTransactionIdSensor(_OcppConnectorSensorBase, RestoreSensor):
    """Transaktions-ID der letzten Session auf diesem Connector, aktiv oder bereits beendet.

    Über einen HA-Neustart hinweg wird der zuletzt bekannte Wert per ``RestoreSensor``
    wiederhergestellt, bis diese Prozesslaufzeit selbst eine Transaktion auf diesem Connector sieht
    -- danach gewinnt immer der Live-Wert (Entscheidung 2026-08-21, siehe DECISIONS.md, analog zu
    ``number.power_limit_w``: zuletzt bekannt, nicht live garantiert).
    """

    _attr_translation_key = "last_transaction_id"

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "last_transaction_id")
        self._restored_value: int | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known transaction id across a HA restart, if one was ever recorded."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, int | float):
            self._restored_value = int(last_data.native_value)

    @property
    def native_value(self) -> int | None:
        """Return the last transaction's id, or the restored value if none happened yet this run."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        if transaction is not None:
            return transaction.transaction_id
        return self._restored_value
