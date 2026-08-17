"""Diagnostic sensor descriptions for occp."""

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE, EntityCategory, UnitOfTime

from .entity import OccpSensorEntityDescription

ENTITY_DESCRIPTIONS: tuple[OccpSensorEntityDescription, ...] = (
    OccpSensorEntityDescription(
        key="filter_life",
        translation_key="filter_life",
        entity_category=EntityCategory.DIAGNOSTIC,
        native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("filter_life"),
    ),
    OccpSensorEntityDescription(
        key="runtime",
        translation_key="runtime",
        entity_category=EntityCategory.DIAGNOSTIC,
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.HOURS,
        state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=0,
        value_fn=lambda data: data.get("runtime"),
    ),
)
