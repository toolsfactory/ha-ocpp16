"""Anzahl Reconnects/Übernahmen seit Prozessstart (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import SensorStateClass
from homeassistant.const import EntityCategory

from ._base import _OcppChargePointSensorBase


class OcppReconnectCountSensor(_OcppChargePointSensorBase):
    """Wie oft sich dieser Charge Point seit Prozessstart erneut verbunden hat.

    Zählt jede Verbindung nach der ersten (saubere Reconnects und REQ-0001-AC4-Übernahmen
    gleichermaßen, siehe ``registry.register_connection``) -- ein Diagnosewert, kein primärer
    Ladezustand, daher ``EntityCategory.DIAGNOSTIC``.
    """

    _attr_translation_key = "reconnect_count"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str) -> None:
        """Initialize the entity for the given charge point."""
        super().__init__(coordinator, entry_data, charge_point_id, "reconnect_count")

    @property
    def native_value(self) -> int | None:
        """Return this charge point's reconnect count."""
        for cp in self._entry_data.app.query_service.get_charge_points():
            if cp.charge_point_id == self._charge_point_id:
                return cp.reconnect_count
        return None
