"""
Runtime data types for occp.

Access pattern: entry.runtime_data.client / entry.runtime_data.coordinator
"""

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.loader import Integration

    from .api import OccpApiClient
    from .coordinator import OccpDataUpdateCoordinator


type OccpConfigEntry = ConfigEntry[OccpData]


@dataclass
class OccpData:
    """Runtime data stored on the config entry after a successful setup."""

    client: OccpApiClient
    coordinator: OccpDataUpdateCoordinator
    integration: Integration
