"""Garantiert vorhandene Ist-Ladeleistungs-Entity (Fähigkeit 1, REQ-0035 AC1)."""

from custom_components.occp.coordinator import OccpCoordinator
from custom_components.occp.runtime import OccpEntryData
from custom_components.occp.utils import interop
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower

from ._base import _OccpConnectorSensorBase


class OccpCurrentPowerSensor(_OccpConnectorSensorBase):
    """Garantiert vorhandene Ist-Ladeleistungs-Entity.

    Fähigkeit 1 des Interop-Vertrags (REQ-0035 AC1), unabhängig von den
    dynamischen Measurand-Sensoren aus REQ-0018.
    """

    _attr_translation_key = "current_power_w"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: OccpCoordinator, entry_data: OccpEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "current_power_w")

    @property
    def native_value(self) -> float | None:
        """Return the connector's current charging power in watts."""
        return interop.get_current_power_w(
            self._entry_data.app.query_service, self._charge_point_id, self._connector_id
        )

    @property
    def available(self) -> bool:
        """Return whether the connection is online and a power value was reported."""
        # REQ-0035 AC1: unavailable, sofern kein passender Messwert gemeldet
        # wurde -- zusätzlich zur allgemeinen Online-Prüfung der Basisklasse.
        return super().available and self.native_value is not None
