"""Dynamischer Sensor je tatsächlich gemeldetem Measurand (REQ-0018)."""

import logging
from typing import Any

from custom_components.occp.coordinator import OccpCoordinator
from custom_components.occp.core.domain.models import MeterSample
from custom_components.occp.runtime import OccpEntryData
from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.helpers.typing import StateType

from ._base import _OccpConnectorSensorBase

_LOGGER = logging.getLogger(__name__)

# REQ-0018 AC3: Gesamtenergiezähler muss mit passender device_class/
# state_class fürs Energie-Dashboard erkennbar sein. Weitere gängige OCPP-1.6-
# Measurands (nicht abschließend -- unbekannte Measurands bekommen keine
# device_class, zeigen aber weiterhin den gemeldeten Rohwert/die Roheinheit).
_MEASURAND_META: dict[str, tuple[SensorDeviceClass | None, SensorStateClass | None]] = {
    "Energy.Active.Import.Register": (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "Energy.Active.Export.Register": (SensorDeviceClass.ENERGY, SensorStateClass.TOTAL_INCREASING),
    "Power.Active.Import": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "Power.Active.Export": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
    "Current.Import": (SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    "Current.Export": (SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    "Current.Offered": (SensorDeviceClass.CURRENT, SensorStateClass.MEASUREMENT),
    "Voltage": (SensorDeviceClass.VOLTAGE, SensorStateClass.MEASUREMENT),
    "Temperature": (SensorDeviceClass.TEMPERATURE, SensorStateClass.MEASUREMENT),
    "SoC": (SensorDeviceClass.BATTERY, SensorStateClass.MEASUREMENT),
    "Power.Offered": (SensorDeviceClass.POWER, SensorStateClass.MEASUREMENT),
}

_UNIT_OVERRIDES: dict[str, str] = {
    "Wh": UnitOfEnergy.WATT_HOUR,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "kW": UnitOfPower.KILO_WATT,
    "A": UnitOfElectricCurrent.AMPERE,
    "V": UnitOfElectricPotential.VOLT,
    "Celsius": UnitOfTemperature.CELSIUS,
    "Fahrenheit": UnitOfTemperature.FAHRENHEIT,
    "Percent": PERCENTAGE,
}


def _measurand_object_id(measurand: str, phase: str | None) -> str:
    slug = measurand.lower().replace(".", "_")
    return f"{slug}_{phase.lower()}" if phase else slug


class OccpMeasurandSensor(_OccpConnectorSensorBase):
    """Dynamischer Sensor je tatsächlich gemeldetem Measurand (REQ-0018).

    Optional nach Phase unterschieden, falls der Charge Point das meldet.
    """

    def __init__(
        self,
        coordinator: OccpCoordinator,
        entry_data: OccpEntryData,
        charge_point_id: str,
        connector_id: int,
        measurand: str,
        phase: str | None,
    ) -> None:
        """Initialize the entity for the given measurand/phase pair."""
        entity_key = f"measurand_{_measurand_object_id(measurand, phase)}"
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, entity_key)
        self._measurand = measurand
        self._phase = phase
        self._attr_name = f"{measurand}{f' ({phase})' if phase else ''}"
        device_class, state_class = _MEASURAND_META.get(measurand, (None, None))
        self._attr_device_class = device_class
        self._attr_state_class = state_class

    @property
    def _sample(self) -> MeterSample | None:
        samples = self._entry_data.app.query_service.get_meter_samples(
            charge_point_id=self._charge_point_id, connector_id=self._connector_id
        )
        matching = [s for s in samples if s.measurand == self._measurand and s.phase == self._phase]
        if not matching:
            return None
        return max(matching, key=lambda s: s.recorded_at)

    @property
    def native_value(self) -> StateType:
        """Return the most recently reported sample value.

        Parsed to ``float`` whenever a ``state_class`` is set -- Home
        Assistant's recorder requires a numeric value for statistics, and
        every measurand in ``_MEASURAND_META`` (the only ones that get a
        ``state_class``) is numeric per OCPP 1.6. Unmapped measurands have no
        ``state_class`` and keep the raw string.
        """
        sample = self._sample
        if sample is None:
            return None
        if self._attr_state_class is None:
            return sample.value
        try:
            return float(sample.value)
        except ValueError:
            _LOGGER.debug(
                "Nicht-numerischer Wert %r für Measurand %s (Connector %s/%s), wird ignoriert.",
                sample.value,
                self._measurand,
                self._charge_point_id,
                self._connector_id,
            )
            return None

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the sample's unit, mapped to HA's unit constants where known."""
        sample = self._sample
        if sample is None or sample.unit is None:
            return None
        return _UNIT_OVERRIDES.get(sample.unit, sample.unit)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the sample's reporting context."""
        sample = self._sample
        return {"context": sample.context if sample else None}
