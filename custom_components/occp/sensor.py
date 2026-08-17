"""Sensor-Plattform.

Dynamische Measurand-Sensoren (REQ-0018), die garantierten Fähigkeit-1/5-
Entities (REQ-0035) und die Status-Entity (REQ-0019, inkl.
Fähigkeit-7-Discovery-Attribute) -- Aufbau/Auffindung neuer Charge
Points/Connectors/Measurands folgt dem Push-Modell aus ADR-0008 Abschnitt 2
(jede Entity liest bei jedem Dispatcher-Ereignis ihren eigenen Ausschnitt
frisch aus ``QueryService``/``CommandService``).
"""

import logging
from typing import Any

from custom_components.occp.core.domain.models import ConnectionStatus, MeterSample, QueryService, StateChangeEvent
from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import interop
from .const import (
    RAW_STATUS_TO_STATE,
    STATE_ERROR,
    SUPPORTED_CAPABILITIES,
    SUPPORTED_PHASES,
    signal_new_charge_point,
    signal_state_update,
)
from .device import connector_device_info
from .runtime import OccpConfigEntry, OccpEntryData

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


async def async_setup_entry(
    hass: HomeAssistant, entry: OccpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities for a config entry."""
    manager = _SensorManager(hass, entry.entry_id, entry.runtime_data, async_add_entities)
    manager.async_setup()


class _SensorManager:
    """Setup-Hilfsobjekt, das Entities dynamisch anlegt.

    Sobald Charge Points/Connectors/Measurands erstmals bekannt werden
    (REQ-0017/REQ-0018) -- selbst keine Entity, sondern reines
    Setup-Hilfsobjekt (vergleichbar einer schlanken, push-basierten
    Alternative zu HA-Discovery-Callbacks).
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: OccpEntryData,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.entry_data = entry_data
        self.async_add_entities = async_add_entities
        self._known_connectors: set[tuple[str, int]] = set()
        self._known_measurands: set[tuple[str, int, str, str | None]] = set()
        self._known_charge_points: set[str] = set()

    def async_setup(self) -> None:
        async_dispatcher_connect(
            self.hass,
            signal_new_charge_point(self.entry_id),
            self._async_add_charge_point,
        )
        # Race zwischen app.start() und Plattform-Forward abdecken (ADR-0008):
        # bereits bekannte Charge Points direkt beim Plattform-Setup aufnehmen.
        for snapshot in self.entry_data.app.query_service.get_charge_points():
            self._async_add_charge_point(snapshot.charge_point_id)

    @callback
    def _async_add_charge_point(self, charge_point_id: str) -> None:
        if charge_point_id in self._known_charge_points:
            return
        self._known_charge_points.add(charge_point_id)

        async_dispatcher_connect(
            self.hass,
            signal_state_update(self.entry_id, charge_point_id),
            callback(lambda event: self._handle_event(charge_point_id, event)),
        )
        self._sync_connectors(charge_point_id)

    @callback
    def _handle_event(self, charge_point_id: str, event: StateChangeEvent) -> None:
        self._sync_connectors(charge_point_id, only_connector_id=event.connector_id)

    def _sync_connectors(self, charge_point_id: str, only_connector_id: int | None = None) -> None:
        query_service = self.entry_data.app.query_service
        if only_connector_id is not None:
            connector_ids = [only_connector_id]
        else:
            connector_ids = [c.connector_id for c in query_service.get_connectors(charge_point_id)]

        new_entities: list[SensorEntity] = []
        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008: connectorId 0 hat kein eigenes Sub-Device.
            key = (charge_point_id, connector_id)
            if key not in self._known_connectors:
                self._known_connectors.add(key)
                new_entities.extend(
                    [
                        OccpChargePointStateSensor(self.entry_id, self.entry_data, charge_point_id, connector_id),
                        OccpCurrentPowerSensor(self.entry_id, self.entry_data, charge_point_id, connector_id),
                        OccpEffectivePowerLimitSensor(self.entry_id, self.entry_data, charge_point_id, connector_id),
                    ]
                )
            new_entities.extend(self._new_measurand_sensors(charge_point_id, connector_id))

        if new_entities:
            self.async_add_entities(new_entities)

    def _new_measurand_sensors(self, charge_point_id: str, connector_id: int) -> list[OccpMeasurandSensor]:
        samples = self.entry_data.app.query_service.get_meter_samples(
            charge_point_id=charge_point_id, connector_id=connector_id
        )
        new_sensors = []
        for sample in samples:
            key = (charge_point_id, connector_id, sample.measurand, sample.phase)
            if key in self._known_measurands:
                continue
            self._known_measurands.add(key)
            new_sensors.append(
                OccpMeasurandSensor(
                    self.entry_id,
                    self.entry_data,
                    charge_point_id,
                    connector_id,
                    sample.measurand,
                    sample.phase,
                )
            )
        return new_sensors


def _is_charge_point_online(query_service: QueryService, charge_point_id: str) -> bool:
    snapshot = query_service.get_charge_points()
    for cp in snapshot:
        if cp.charge_point_id == charge_point_id:
            return cp.connection_status == ConnectionStatus.ONLINE
    return False


class _OccpConnectorSensorBase(SensorEntity):
    """Gemeinsame Basis aller connectorbezogenen Sensor-Entities.

    Push-only (``_attr_should_poll = False``, ``iot_class: local_push``):
    jede Instanz abonniert in ``async_added_to_hass`` das Dispatcher-Signal
    für ihren Charge Point und liest bei jedem Ereignis ihren Ausschnitt
    frisch aus ``QueryService``/``CommandService`` (ADR-0008 Abschnitt 2).
    """

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        entry_data: OccpEntryData,
        charge_point_id: str,
        connector_id: int,
        entity_key: str,
    ) -> None:
        self._entry_id = entry_id
        self._entry_data = entry_data
        self._charge_point_id = charge_point_id
        self._connector_id = connector_id
        self._attr_unique_id = f"{charge_point_id}_{connector_id}_{entity_key}"
        self._attr_device_info = connector_device_info(charge_point_id, connector_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_state_update(self._entry_id, self._charge_point_id),
                self._async_handle_event,
            )
        )

    async def _async_handle_event(self, event: StateChangeEvent) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return _is_charge_point_online(self._entry_data.app.query_service, self._charge_point_id)


class OccpCurrentPowerSensor(_OccpConnectorSensorBase):
    """Garantiert vorhandene Ist-Ladeleistungs-Entity.

    Fähigkeit 1 des Interop-Vertrags (REQ-0035 AC1), unabhängig von den
    dynamischen Measurand-Sensoren aus REQ-0018.
    """

    _attr_translation_key = "current_power_w"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, entry_id: str, entry_data: OccpEntryData, charge_point_id: str, connector_id: int) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, "current_power_w")

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


class OccpEffectivePowerLimitSensor(_OccpConnectorSensorBase):
    """Wirksame Leistungsgrenze über ``GetCompositeSchedule``.

    Fähigkeit 5 des Interop-Vertrags (REQ-0035 AC4) -- erfordert einen
    Central-System-initiierten Aufruf, deshalb asynchron im
    Dispatcher-Callback aktualisiert und zwischengespeichert (ADR-0010).
    """

    _attr_translation_key = "effective_power_limit_w"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(self, entry_id: str, entry_data: OccpEntryData, charge_point_id: str, connector_id: int) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, "effective_power_limit_w")
        self._value: float | None = None

    async def _async_handle_event(self, event: StateChangeEvent) -> None:
        if event.connector_id is not None and event.connector_id != self._connector_id:
            # Kein charge-point-weites Ereignis und nicht für diesen Connector --
            # ein GetCompositeSchedule-Aufruf hier wäre nur unnötiger Central-
            # System-initiierter Traffic zum Charge Point.
            return
        try:
            self._value = await interop.get_effective_power_limit_w(
                self._entry_data.app.command_service,
                self._charge_point_id,
                self._connector_id,
            )
        except Exception:
            # Central-System-initiierter Aufruf kann jederzeit fehlschlagen
            # (z. B. Charge Point trennt gerade die Verbindung) -- ein
            # einzelner fehlgeschlagener GetCompositeSchedule-Versuch darf
            # nicht den gesamten Dispatcher-Callback (und damit andere
            # Entities desselben Signals) zum Absturz bringen.
            _LOGGER.debug(
                "GetCompositeSchedule für %s/%s fehlgeschlagen, Wert bleibt unverändert.",
                self._charge_point_id,
                self._connector_id,
                exc_info=True,
            )
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | None:
        """Return the connector's last fetched effective power limit in watts."""
        return self._value


class OccpChargePointStateSensor(_OccpConnectorSensorBase):
    """Fünfwertiges Statusmodell als Hauptzustand (REQ-0019).

    Roher OCPP-1.6-Status + Fähigkeit-7-Discovery-Attribute als Attribute.
    """

    _attr_translation_key = "charge_point_state"
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = list(dict.fromkeys(RAW_STATUS_TO_STATE.values()))

    def __init__(self, entry_id: str, entry_data: OccpEntryData, charge_point_id: str, connector_id: int) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, "charge_point_state")

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


def _measurand_object_id(measurand: str, phase: str | None) -> str:
    slug = measurand.lower().replace(".", "_")
    return f"{slug}_{phase.lower()}" if phase else slug


class OccpMeasurandSensor(_OccpConnectorSensorBase):
    """Dynamischer Sensor je tatsächlich gemeldetem Measurand (REQ-0018).

    Optional nach Phase unterschieden, falls der Charge Point das meldet.
    """

    def __init__(
        self,
        entry_id: str,
        entry_data: OccpEntryData,
        charge_point_id: str,
        connector_id: int,
        measurand: str,
        phase: str | None,
    ) -> None:
        """Initialize the entity for the given measurand/phase pair."""
        entity_key = f"measurand_{_measurand_object_id(measurand, phase)}"
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, entity_key)
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
    def native_value(self) -> str | None:
        """Return the most recently reported sample value."""
        sample = self._sample
        return sample.value if sample else None

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
