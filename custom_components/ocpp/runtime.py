"""Laufzeitdaten je Config Entry (``entry.runtime_data``).

Eigenes, kleines Modul statt Definition in ``__init__.py``, damit
``sensor.py``/``switch.py``/``services.py`` es importieren können, ohne einen
Importzyklus mit ``__init__.py`` (das seinerseits Entity-Plattformen anstößt)
zu erzeugen.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from custom_components.ocpp.core.app import CentralSystemApp
from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    # Nur für Typprüfung: würde zur Laufzeit einen Zyklus mit
    # coordinator.coordinator (importiert seinerseits diesen Typalias nicht,
    # aber der Zyklus entstünde trivial bei künftigen Refactorings) erzeugen.
    from .coordinator import OcppCoordinator


@dataclass
class OcppEntryData:
    """Pro Config Entry gehaltener Zustand des HA-Layers."""

    app: CentralSystemApp
    coordinator: OcppCoordinator
    default_id_tag: str | None
    entry_id: str


type OcppConfigEntry = ConfigEntry[OcppEntryData]
