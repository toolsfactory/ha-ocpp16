"""Laufzeitdaten je Config Entry (``hass.data[DOMAIN][entry.entry_id]``).

Eigenes, kleines Modul statt Definition in ``__init__.py``, damit
``sensor.py``/``switch.py``/``services.py`` es importieren können, ohne einen
Importzyklus mit ``__init__.py`` (das seinerseits Entity-Plattformen anstößt)
zu erzeugen.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from custom_components.occp.core.app import CentralSystemApp


@dataclass
class OccpEntryData:
    """Pro Config Entry gehaltener Zustand des HA-Layers."""

    app: CentralSystemApp
    default_id_tag: str | None
    # REQ-0017 AC1: Entity-Anlage erfolgt erst, wenn ein Charge Point
    # tatsächlich erstmals eine StateChangeEvent auslöst (siehe
    # ``const.signal_new_charge_point``) -- dieses Set verhindert doppelte
    # "neuer Charge Point"-Dispatcher-Signale für bereits bekannte IDs.
    known_charge_points: set[str] = field(default_factory=set)
