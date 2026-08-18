"""Gemeinsame Basis aller connectorbezogenen Sensor-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Sensor-Klassen aus den Geschwistermodulen für ``_SensorManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.occp.entity import OccpConnectorEntity
from homeassistant.components.sensor import SensorEntity


class _OccpConnectorSensorBase(OccpConnectorEntity, SensorEntity):
    """Gemeinsame Basis aller connectorbezogenen Sensor-Entities."""
