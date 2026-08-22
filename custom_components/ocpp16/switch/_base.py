"""Gemeinsame Basis aller connectorbezogenen Switch-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Switch-Klassen aus den Geschwistermodulen für ``_SwitchManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp16.entity import Ocpp16ConnectorEntity
from homeassistant.components.switch import SwitchEntity


class _OcppConnectorSwitchBase(Ocpp16ConnectorEntity, SwitchEntity):
    """Gemeinsame Basis aller connectorbezogenen Switch-Entities."""
