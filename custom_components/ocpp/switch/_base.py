"""Gemeinsame Basis aller connectorbezogenen Switch-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Switch-Klassen aus den Geschwistermodulen für ``_SwitchManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp.entity import OcppConnectorEntity
from homeassistant.components.switch import SwitchEntity


class _OcppConnectorSwitchBase(OcppConnectorEntity, SwitchEntity):
    """Gemeinsame Basis aller connectorbezogenen Switch-Entities."""
