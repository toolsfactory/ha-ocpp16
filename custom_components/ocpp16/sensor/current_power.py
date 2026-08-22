"""Garantiert vorhandene Ist-Ladeleistungs-Entity (Fähigkeit 1, REQ-0035 AC1)."""

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.runtime import Ocpp16EntryData
from custom_components.ocpp16.utils import interop
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfPower

from ._base import _OcppConnectorSensorBase


class Ocpp16CurrentPowerSensor(_OcppConnectorSensorBase):
    """Garantiert vorhandene Ist-Ladeleistungs-Entity.

    Fähigkeit 1 des Interop-Vertrags (REQ-0035 AC1), unabhängig von den
    dynamischen Measurand-Sensoren aus REQ-0018.

    ``available`` folgt der Basisklasse (nur Online-Status) statt eigens zu
    ``unavailable`` zu werden, solange kein passender Messwert gemeldet
    wurde -- ``unavailable`` bedeutet nach HA-Konvention "nicht erreichbar",
    nicht "Einzelwert fehlt noch". Ein fehlender Wert liefert stattdessen
    ``unknown`` über ``native_value -> None``.
    """

    _attr_translation_key = "current_power_w"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "current_power_w")

    @property
    def native_value(self) -> float | None:
        """Return the connector's current charging power in watts, or `None` if none has been reported yet."""
        return interop.get_current_power_w(
            self._entry_data.app.query_service, self._charge_point_id, self._connector_id
        )
