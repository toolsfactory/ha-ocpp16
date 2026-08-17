"""Sensor entity for occp."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from custom_components.occp.entity import OccpEntity
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.helpers.typing import StateType


@dataclass(frozen=True, kw_only=True)
class OccpSensorEntityDescription(SensorEntityDescription):
    """Describes a sensor and how to read it from coordinator data."""

    value_fn: Callable[[dict[str, Any]], StateType]


class OccpSensor(SensorEntity, OccpEntity):
    """Sensor backed by one value in the coordinator payload."""

    entity_description: OccpSensorEntityDescription

    @property
    def native_value(self) -> StateType:
        """Return the value read from coordinator data."""
        return self.entity_description.value_fn(self.coordinator.data)
