"""Fünfwertiges Statusmodell als Hauptzustand (REQ-0019)."""

from typing import Any

from custom_components.ocpp16.const import RAW_STATUS_TO_STATE, STATE_ERROR, SUPPORTED_CAPABILITIES, SUPPORTED_PHASES
from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.components.sensor import SensorDeviceClass

from ._base import _OcppConnectorSensorBase


class Ocpp16ChargePointStateSensor(_OcppConnectorSensorBase):
    """Fünfwertiges Statusmodell als Hauptzustand (REQ-0019).

    Roher OCPP-1.6-Status + Fähigkeit-7-Discovery-Attribute als Attribute.
    """

    _attr_translation_key = "charge_point_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(dict.fromkeys(RAW_STATUS_TO_STATE.values()))

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "charge_point_state")

    @property
    def _connector_snapshot(self):
        return self._entry_data.app.query_service.get_connector(self._charge_point_id, self._connector_id)

    @property
    def native_value(self) -> str | None:
        """Return the connector's status mapped to the five-value state model."""
        snapshot = self._connector_snapshot
        if snapshot is None:
            return None
        return RAW_STATUS_TO_STATE.get(snapshot.status, STATE_ERROR)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the raw OCPP status and the capability-7 discovery attributes."""
        snapshot = self._connector_snapshot
        return {
            "raw_ocpp_status": snapshot.status if snapshot else None,
            "error_code": snapshot.error_code if snapshot else None,
            "supported_capabilities": SUPPORTED_CAPABILITIES,
            "min_power_limit_w": None,  # ADR-0010: OCPP 1.6 bietet keine
            "max_power_limit_w": None,  # generische Abfragemöglichkeit.
            "supported_phases": SUPPORTED_PHASES,
        }
