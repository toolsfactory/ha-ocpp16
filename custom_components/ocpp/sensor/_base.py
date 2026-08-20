"""Gemeinsame Basis aller connectorbezogenen Sensor-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Sensor-Klassen aus den Geschwistermodulen für ``_SensorManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp.entity import OcppChargePointEntity, OcppConnectorEntity
from homeassistant.components.sensor import SensorEntity


class _OcppConnectorSensorBase(OcppConnectorEntity, SensorEntity):
    """Gemeinsame Basis aller connectorbezogenen Sensor-Entities."""


class _OcppChargePointSensorBase(OcppChargePointEntity, SensorEntity):
    """Gemeinsame Basis aller charge-point-weiten Sensor-Entities."""
