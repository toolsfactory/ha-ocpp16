"""Gemeinsame Basis aller connectorbezogenen Number-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Number-Klassen aus den Geschwistermodulen für ``_NumberManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp.entity import OcppConnectorEntity
from homeassistant.components.number import NumberEntity


class _OcppConnectorNumberBase(OcppConnectorEntity, NumberEntity):
    """Gemeinsame Basis aller connectorbezogenen Number-Entities."""
