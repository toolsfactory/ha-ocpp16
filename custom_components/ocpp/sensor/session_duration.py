"""Dauer der letzten (aktiven oder beendeten) Session (kein Interop-Vertrag-Bestandteil)."""

from datetime import UTC, datetime

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfTime

from ._base import _OcppConnectorSensorBase


class OcppSessionDurationSensor(_OcppConnectorSensorBase):
    """Dauer der letzten Session -- bis jetzt, falls sie noch läuft, sonst bis zu ihrem Ende.

    Push-only wie jede andere Entity hier (ADR-0008 Abschnitt 2): der Wert wird bei jedem
    Coordinator-Update frisch berechnet, tickt also nicht sekündlich, sondern aktualisiert sich mit
    jedem StatusNotification/MeterValues/StopTransaction-Ereignis auf diesem Connector.
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

    @property
    def native_value(self) -> float | None:
        """Return the last session's duration in seconds, or `None` if this connector never had one."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        if transaction is None:
            return None
        end = transaction.stopped_at or datetime.now(UTC)
        return (end - transaction.started_at).total_seconds()
