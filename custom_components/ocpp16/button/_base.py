"""Gemeinsame Basis aller Button-Entities.

Eigenes Modul statt in ``__init__.py`` -- ``__init__.py`` importiert die
konkreten Button-Klassen aus den Geschwistermodulen für ``_ButtonManager``,
ein Import in Gegenrichtung würde einen Zirkelimport erzeugen.
"""

from custom_components.ocpp16.entity import Ocpp16ChargePointEntity, Ocpp16ConnectorEntity
from homeassistant.components.button import ButtonEntity


class _OcppConnectorButtonBase(Ocpp16ConnectorEntity, ButtonEntity):
    """Gemeinsame Basis aller connectorbezogenen Button-Entities."""


class _OcppChargePointButtonBase(Ocpp16ChargePointEntity, ButtonEntity):
    """Gemeinsame Basis aller charge-point-weiten Button-Entities."""
