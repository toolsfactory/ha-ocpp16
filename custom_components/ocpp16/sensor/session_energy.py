"""Gelieferte Energie der letzten (aktiven oder beendeten) Session (kein Interop-Vertrag-Bestandteil)."""

from custom_components.ocpp16.const import MEASURAND_ENERGY_ACTIVE_IMPORT_REGISTER
from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.core.domain.models import MeterSample, TransactionSnapshot
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorStateClass
from homeassistant.const import UnitOfEnergy

from ._base import _OcppConnectorSensorBase

# W/kW-Multiplikatoren-Idee aus utils/interop.py's _parse_power_w gespiegelt, hier lokal statt dort:
# Session-Energie ist kein REQ-0035-Vertragsbestandteil (siehe ADR-0010), utils/interop.py bleibt
# auf die dortigen Fähigkeiten beschränkt.
_ENERGY_UNIT_MULTIPLIERS: dict[str, float] = {
    "Wh": 1.0,
    "kWh": 1000.0,
}


def _parse_energy_wh(sample: MeterSample) -> float | None:
    try:
        value = float(sample.value)
    except ValueError:
        return None
    multiplier = _ENERGY_UNIT_MULTIPLIERS.get(sample.unit or "Wh", 1.0)
    return value * multiplier


class Ocpp16SessionEnergySensor(_OcppConnectorSensorBase, RestoreSensor):
    """Gelieferte Energie der letzten Session in Wh.

    Beendet: ``meter_stop_wh - meter_start_wh`` (bereits von OCPP in Wh gemeldet). Aktiv: letzter
    phasenloser ``Energy.Active.Import.Register``-Messwert dieser Transaktion minus
    ``meter_start_wh`` -- ``unknown`` (nicht ``0``), solange noch kein solcher Messwert einging
    (Konvention wie ``current_power_w``/``effective_power_limit_w``).

    Über einen HA-Neustart hinweg wird der zuletzt bekannte Wert per ``RestoreSensor``
    wiederhergestellt, bis diese Prozesslaufzeit selbst eine Transaktion auf diesem Connector sieht
    -- eine zum Neustart-Zeitpunkt noch aktive Session bleibt bis dahin auf dem wiederhergestellten
    Wert eingefroren statt live weiterzuzählen.
    """

    _attr_translation_key = "session_energy_wh"
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_native_unit_of_measurement = UnitOfEnergy.WATT_HOUR
    # TOTAL, nicht TOTAL_INCREASING: dieser Wert setzt mit jeder neuen Session neu bei ~0 auf,
    # anders als der lebenslang monoton steigende Energy.Active.Import.Register-Measurand-Sensor.
    _attr_state_class = SensorStateClass.TOTAL

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "session_energy_wh")
        self._restored_value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last known session energy across a HA restart, if one was ever recorded."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_sensor_data()
        if last_data is not None and isinstance(last_data.native_value, int | float):
            self._restored_value = float(last_data.native_value)

    def _current_energy_wh(self, transaction: TransactionSnapshot) -> float | None:
        samples = self._entry_data.app.query_service.get_meter_samples(
            charge_point_id=self._charge_point_id, transaction_id=transaction.transaction_id
        )
        matching = [s for s in samples if s.measurand == MEASURAND_ENERGY_ACTIVE_IMPORT_REGISTER and s.phase is None]
        if not matching:
            return None
        latest = max(matching, key=lambda s: s.recorded_at)
        return _parse_energy_wh(latest)

    @property
    def native_value(self) -> float | None:
        """Return the last session's delivered energy in Wh, or the restored value if none ran yet."""
        transaction = self._entry_data.app.query_service.get_last_transaction(self._charge_point_id, self._connector_id)
        if transaction is None:
            return self._restored_value
        if transaction.stopped_at is not None:
            meter_stop_wh = transaction.meter_stop_wh
            if meter_stop_wh is None:
                return None
            return float(meter_stop_wh - transaction.meter_start_wh)
        current_wh = self._current_energy_wh(transaction)
        if current_wh is None:
            return None
        return current_wh - transaction.meter_start_wh
