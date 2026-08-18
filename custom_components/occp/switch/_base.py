"""Gemeinsame Basis aller connectorbezogenen Switch-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Switch-Klassen aus den Geschwistermodulen für ``_SwitchManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.occp.entity import OccpConnectorEntity
from homeassistant.components.switch import SwitchEntity


class _OccpConnectorSwitchBase(OccpConnectorEntity, SwitchEntity):
    """Gemeinsame Basis aller connectorbezogenen Switch-Entities."""
