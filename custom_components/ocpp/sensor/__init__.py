"""Sensor-Plattform.

Dynamische Measurand-Sensoren (REQ-0018), die garantierten Fähigkeit-1/5-
Entities (REQ-0035) und die Status-Entity (REQ-0019, inkl.
Fähigkeit-7-Discovery-Attribute) -- Aufbau/Auffindung neuer Charge
Points/Connectors/Measurands folgt dem Push-Modell aus ADR-0008 Abschnitt 2
über den ``OcppCoordinator`` (jede Entity liest bei jedem Coordinator-Update
ihren eigenen Ausschnitt frisch aus ``QueryService``/``CommandService``).
"""

from custom_components.ocpp.runtime import OcppConfigEntry, OcppEntryData
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .active_phases import OcppActivePhasesSensor
from .charge_point_state import OcppChargePointStateSensor
from .current_power import OcppCurrentPowerSensor
from .effective_power_limit import OcppEffectivePowerLimitSensor
from .measurand import OcppMeasurandSensor

# Rein lesend -- jede Entity liest bei jedem Dispatcher-Ereignis ihren eigenen
# Ausschnitt, kein eigener I/O-Aufruf (siehe Moduldocstring).
PARALLEL_UPDATES = 0

__all__ = [
    "OcppActivePhasesSensor",
    "OcppChargePointStateSensor",
    "OcppCurrentPowerSensor",
    "OcppEffectivePowerLimitSensor",
    "OcppMeasurandSensor",
    "async_setup_entry",
]


async def async_setup_entry(
    hass: HomeAssistant, entry: OcppConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities for a config entry."""
    manager = _SensorManager(entry.runtime_data, async_add_entities)
    entry.async_on_unload(manager.async_setup())


class _SensorManager:
    """Setup-Hilfsobjekt, das Entities dynamisch anlegt.

    Sobald Charge Points/Connectors/Measurands erstmals bekannt werden
    (REQ-0017/REQ-0018) -- selbst keine Entity, sondern reines
    Setup-Hilfsobjekt (vergleichbar einer schlanken, push-basierten
    Alternative zu HA-Discovery-Callbacks). Reagiert auf ``OcppCoordinator``-
    Updates statt eigener Dispatcher-Signale.
    """

    def __init__(self, entry_data: OcppEntryData, async_add_entities: AddEntitiesCallback) -> None:
        self.entry_data = entry_data
        self.coordinator = entry_data.coordinator
        self.async_add_entities = async_add_entities
        self._known_connectors: set[tuple[str, int]] = set()
        self._known_measurands: set[tuple[str, int, str, str | None]] = set()

    def async_setup(self) -> CALLBACK_TYPE:
        """Start listening and sync already-known charge points. Returns the coordinator unsubscribe callable."""
        remove_listener = self.coordinator.async_add_listener(self._handle_coordinator_update)
        # Race zwischen app.start() und Plattform-Forward abdecken (ADR-0008):
        # bereits bekannte Charge Points direkt beim Plattform-Setup aufnehmen.
        for snapshot in self.entry_data.app.query_service.get_charge_points():
            self._sync_connectors(snapshot.charge_point_id)
        return remove_listener

    @callback
    def _handle_coordinator_update(self) -> None:
        event = self.coordinator.data
        if event is None:
            return
        self._sync_connectors(event.charge_point_id, only_connector_id=event.connector_id)

    def _sync_connectors(self, charge_point_id: str, only_connector_id: int | None = None) -> None:
        query_service = self.entry_data.app.query_service
        if only_connector_id is not None:
            connector_ids = [only_connector_id]
        else:
            connector_ids = [c.connector_id for c in query_service.get_connectors(charge_point_id)]

        new_entities: list[
            OcppActivePhasesSensor
            | OcppChargePointStateSensor
            | OcppCurrentPowerSensor
            | OcppEffectivePowerLimitSensor
            | OcppMeasurandSensor
        ] = []
        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008: connectorId 0 hat kein eigenes Sub-Device.
            key = (charge_point_id, connector_id)
            if key not in self._known_connectors:
                self._known_connectors.add(key)
                new_entities.extend(
                    [
                        OcppChargePointStateSensor(self.coordinator, self.entry_data, charge_point_id, connector_id),
                        OcppCurrentPowerSensor(self.coordinator, self.entry_data, charge_point_id, connector_id),
                        OcppEffectivePowerLimitSensor(self.coordinator, self.entry_data, charge_point_id, connector_id),
                        OcppActivePhasesSensor(self.coordinator, self.entry_data, charge_point_id, connector_id),
                    ]
                )
            new_entities.extend(self._new_measurand_sensors(charge_point_id, connector_id))

        if new_entities:
            self.async_add_entities(new_entities)

    def _new_measurand_sensors(self, charge_point_id: str, connector_id: int) -> list[OcppMeasurandSensor]:
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
                OcppMeasurandSensor(
                    self.coordinator,
                    self.entry_data,
                    charge_point_id,
                    connector_id,
                    sample.measurand,
                    sample.phase,
                )
            )
        return new_sensors
