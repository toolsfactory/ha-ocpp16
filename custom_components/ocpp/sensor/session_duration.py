"""Dauer der letzten (aktiven oder beendeten) Session (kein Interop-Vertrag-Bestandteil)."""

from datetime import UTC, datetime

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTime

from ._base import _OcppConnectorSensorBase


class OcppSessionDurationSensor(_OcppConnectorSensorBase, RestoreSensor):
    """Dauer der letzten Session -- bis jetzt, falls sie noch läuft, sonst bis zu ihrem Ende.

    Push-only wie jede andere Entity hier (ADR-0008 Abschnitt 2): der Wert wird bei jedem
    Coordinator-Update frisch berechnet, tickt also nicht sekündlich, sondern aktualisiert sich mit
    jedem StatusNotification/MeterValues/StopTransaction-Ereignis auf diesem Connector.

    Über einen HA-Neustart hinweg wird der zuletzt bekannte Wert per ``RestoreSensor``
    wiederhergestellt, bis diese Prozesslaufzeit selbst eine Transaktion auf diesem Connector sieht
    -- war die Session beim Neustart noch aktiv, bleibt der wiederhergestellte Wert bis dahin
    eingefroren (kein rekonstruierbarer Startzeitpunkt), statt weiterzuzählen.
    """

    _attr_translation_key = "session_duration_s"
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.SECONDS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "session_duration_s")
        self._restored_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known session duration across a HA restart, if one was ever recorded."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, int | float):
            self._restored_value = float(last_data.native_value)

    @property
    def native_value(self) -> float | None:
        """Return the last session's duration in seconds, or the restored value if none ran yet."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        if transaction is None:
            return self._restored_value
        end = transaction.stopped_at or datetime.now(UTC)
        return (end - transaction.started_at).total_seconds()
