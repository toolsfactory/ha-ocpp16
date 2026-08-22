"""Gemeinsame Basis aller connectorbezogenen Number-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Number-Klassen aus den Geschwistermodulen für ``_NumberManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp16.entity import Ocpp16ConnectorEntity
from homeassistant.components.number import NumberEntity


class _OcppConnectorNumberBase(Ocpp16ConnectorEntity, NumberEntity):
    """Gemeinsame Basis aller connectorbezogenen Number-Entities."""
