"""Gemeinsame Basis aller Button-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Button-Klassen aus den Geschwistermodulen für ``_ButtonManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp.entity import OcppChargePointEntity, OcppConnectorEntity
from homeassistant.components.button import ButtonEntity


class _OcppConnectorButtonBase(OcppConnectorEntity, ButtonEntity):
    """Gemeinsame Basis aller connectorbezogenen Button-Entities."""


class _OcppChargePointButtonBase(OcppChargePointEntity, ButtonEntity):
    """Gemeinsame Basis aller charge-point-weiten Button-Entities."""
