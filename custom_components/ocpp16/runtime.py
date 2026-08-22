"""Laufzeitdaten je Config Entry (``entry.runtime_data``).

Eigenes, kleines Modul statt Definition in ``__init__.py``, damit
``sensor.py``/``switch.py``/``services.py`` es importieren können, ohne einen
Importzyklus mit ``__init__.py`` (das seinerseits Entity-Plattformen anstößt)
zu erzeugen.
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from custom_components.ocpp16.core.app import CentralSystemApp
from homeassistant.config_entries import ConfigEntry

if TYPE_CHECKING:
    # Nur für Typprüfung: würde zur Laufzeit einen Zyklus mit
    # coordinator.coordinator (importiert seinerseits diesen Typalias nicht,
    # aber der Zyklus entstünde trivial bei künftigen Refactorings) erzeugen.
    from .coordinator import Ocpp16Coordinator


@dataclass
class Ocpp16EntryData:
    """Pro Config Entry gehaltener Zustand des HA-Layers."""

    app: CentralSystemApp
    coordinator: Ocpp16Coordinator
    default_id_tag: str | None
    max_power_limit_w: float
    entry_id: str


type Ocpp16ConfigEntry = ConfigEntry[Ocpp16EntryData]
