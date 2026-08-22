"""Sensor-Plattform.

Dynamische Measurand-Sensoren (REQ-0018), die garantierten Fähigkeit-1/5-
Entities (REQ-0035) und die Status-Entity (REQ-0019, inkl.
Fähigkeit-7-Discovery-Attribute) -- Aufbau/Auffindung neuer Charge
Points/Connectors/Measurands folgt dem Push-Modell aus ADR-0008 Abschnitt 2
über den ``Ocpp16Coordinator`` (jede Entity liest bei jedem Coordinator-Update
ihren eigenen Ausschnitt frisch aus ``QueryService``/``CommandService``).
"""

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.entity_utils.dynamic_platform import DynamicPlatformManager
from custom_components.ocpp16.runtime import Ocpp16ConfigEntry, Ocpp16EntryData
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .active_phases import Ocpp16ActivePhasesSensor
from .charge_point_state import Ocpp16ChargePointStateSensor
from .current_power import Ocpp16CurrentPowerSensor
from .effective_power_limit import Ocpp16EffectivePowerLimitSensor
from .last_heartbeat import Ocpp16LastHeartbeatSensor
from .last_stop_reason import Ocpp16LastStopReasonSensor
from .last_transaction_id import Ocpp16LastTransactionIdSensor
from .measurand import Ocpp16MeasurandSensor
from .reconnect_count import Ocpp16ReconnectCountSensor
from .session_duration import Ocpp16SessionDurationSensor
from .session_energy import Ocpp16SessionEnergySensor

# Rein lesend -- jede Entity liest bei jedem Dispatcher-Ereignis ihren eigenen
# Ausschnitt, kein eigener I/O-Aufruf (siehe Moduldocstring).
PARALLEL_UPDATES = 0

__all__ = [
    "Ocpp16ActivePhasesSensor",
    "Ocpp16ChargePointStateSensor",
    "Ocpp16CurrentPowerSensor",
    "Ocpp16EffectivePowerLimitSensor",
    "Ocpp16LastHeartbeatSensor",
    "Ocpp16LastStopReasonSensor",
    "Ocpp16LastTransactionIdSensor",
    "Ocpp16MeasurandSensor",
    "Ocpp16ReconnectCountSensor",
    "Ocpp16SessionDurationSensor",
    "Ocpp16SessionEnergySensor",
    "async_setup_entry",
]


def _connector_entities(
    coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
) -> list[Entity]:
    return [
        Ocpp16ChargePointStateSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16CurrentPowerSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16EffectivePowerLimitSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16ActivePhasesSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16LastTransactionIdSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16SessionDurationSensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16SessionEnergySensor(coordinator, entry_data, charge_point_id, connector_id),
        Ocpp16LastStopReasonSensor(coordinator, entry_data, charge_point_id, connector_id),
    ]


def _charge_point_entities(
    coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str
) -> list[Entity]:
    return [
        Ocpp16LastHeartbeatSensor(coordinator, entry_data, charge_point_id),
        Ocpp16ReconnectCountSensor(coordinator, entry_data, charge_point_id),
    ]


class _MeasurandDiscovery:
    """Per-config-entry state for REQ-0018 measurand sub-discovery.

    Doesn't fit `DynamicPlatformManager`'s "one entity list per connector" shape as a plain
    function -- new measurands can appear on an already-known connector, so this needs its own
    `_known_measurands` tracking, called on every sync regardless of whether the connector itself
    is new.
    """

    def __init__(self) -> None:
        self._known_measurands: set[tuple[str, int, str, str | None]] = set()

    def __call__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> list[Entity]:
        samples = entry_data.app.query_service.get_meter_samples(
            charge_point_id=charge_point_id, connector_id=connector_id
        )
        new_sensors: list[Entity] = []
        for sample in samples:
            key = (charge_point_id, connector_id, sample.measurand, sample.phase)
            if key in self._known_measurands:
                continue
            self._known_measurands.add(key)
            new_sensors.append(
                Ocpp16MeasurandSensor(
                    coordinator, entry_data, charge_point_id, connector_id, sample.measurand, sample.phase
                )
            )
        return new_sensors


async def async_setup_entry(
    hass: HomeAssistant, entry: Ocpp16ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up sensor entities for a config entry."""
    manager = DynamicPlatformManager(
        entry.runtime_data,
        async_add_entities,
        connector_entity_factory=_connector_entities,
        charge_point_entity_factory=_charge_point_entities,
        extra_connector_entity_factory=_MeasurandDiscovery(),
    )
    entry.async_on_unload(manager.async_setup())
