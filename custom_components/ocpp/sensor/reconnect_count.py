"""Anzahl Reconnects/Übernahmen seit Prozessstart (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.components.sensor import RestoreSensor, SensorStateClass
from homeassistant.const import EntityCategory

from ._base import _OcppChargePointSensorBase


class OcppReconnectCountSensor(_OcppChargePointSensorBase, RestoreSensor):
    """Wie oft sich dieser Charge Point seit Prozessstart erneut verbunden hat.

    Zählt jede Verbindung nach der ersten (saubere Reconnects und REQ-0001-AC4-Übernahmen
    gleichermaßen, siehe ``registry.register_connection``) -- ein Diagnosewert, kein primärer
    Ladezustand, daher ``EntityCategory.DIAGNOSTIC``.

    Der Domain-Layer-Zähler selbst startet bei jedem HA-Neustart wieder bei ``0`` (kein
    Persistenzmechanismus in ``registry.py``, unverändert). Über einen HA-Neustart hinweg
    addiert dieser Sensor stattdessen den per ``RestoreSensor`` wiederhergestellten Stand aus
    vorherigen Prozessläufen auf den aktuellen Prozesszähler -- anders als bei den
    Transaktions-Sensoren (die den vorherigen Wert nur bis zur nächsten echten Transaktion zeigen)
    wäre ein reiner Fallback hier falsch, weil sonst bereits gezählte Reconnects nach dem ersten
    Reconnect dieses Prozesses verloren gingen.
    """

    _attr_translation_key = "reconnect_count"
    _attr_state_class = SensorStateClass.TOTAL_INCREASING
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str) -> None:
        """Initialize the entity for the given charge point."""
        super().__init__(coordinator, entry_data, charge_point_id, "reconnect_count")
        self._restored_base = 0

    async def async_added_to_hass(self) -> None:
        """Restore the reconnect count accumulated in previous process runs, if any."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, int | float):
            self._restored_base = int(last_data.native_value)

    @property
    def native_value(self) -> int | None:
        """Return this charge point's reconnect count, including restored previous runs."""
        for cp in self._entry_data.app.query_service.get_charge_points():
            if cp.charge_point_id == self._charge_point_id:
                return self._restored_base + cp.reconnect_count
        return self._restored_base or None
