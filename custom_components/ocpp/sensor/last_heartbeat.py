"""Zeitpunkt des letzten Heartbeat.req (REQ-0018 verwandt, charge-point-weit)."""

from datetime import datetime

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import SensorDeviceClass

from ._base import _OcppChargePointSensorBase


class OcppLastHeartbeatSensor(_OcppChargePointSensorBase):
    """Zeitpunkt des letzten Heartbeat.req dieses Charge Points."""

    _attr_translation_key = "last_heartbeat"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    def __init__(self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str) -> None:
        """Initialize the entity for the given charge point."""
        super().__init__(coordinator, entry_data, charge_point_id, "last_heartbeat")

    @property
    def native_value(self) -> datetime | None:
        """Return the timestamp of the last Heartbeat.req, or `None` if none has arrived yet."""
        for cp in self._entry_data.app.query_service.get_charge_points():
            if cp.charge_point_id == self._charge_point_id:
                return cp.last_heartbeat_at
        return None
