"""OCCP Home-Assistant-Layer.

Verdrahtet ``occp.app.CentralSystemApp`` (aus dem Standalone-Kern,
``src/occp/``) mit Home Assistants Event-Loop, Device-Registry und
Entity-Plattformen (ADR-0008).

Kein ``homeassistant.*``-Import in ``src/occp/`` -- die gesamte HA-Anbindung
lebt ausschließlich hier unter ``custom_components/occp/`` (CLAUDE.md).
"""

import logging
from pathlib import Path

from custom_components.occp.core.app import CentralSystemApp
from custom_components.occp.core.config import AppConfig
from custom_components.occp.core.domain.models import StateChangeEvent
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTHORIZATION_FILE,
    CONF_DEFAULT_ID_TAG,
    CONF_HOST,
    CONF_PORT,
    DOMAIN,
    PLATFORMS,
    signal_new_charge_point,
    signal_state_update,
)
from .device import charge_point_device_info
from .runtime import OccpConfigEntry, OccpEntryData
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the REQ-0035 services once, independent of config entry count."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OccpConfigEntry) -> bool:
    """Build the `CentralSystemApp` and start it on `hass.loop`.

    ADR-0008 Abschnitt 1: ``await app.start()`` genügt, kein
    ``hass.async_create_task`` -- ``start()`` selbst blockiert nicht.
    """
    authorization_file = entry.data.get(CONF_AUTHORIZATION_FILE)
    config = AppConfig(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        authorization_file=Path(authorization_file) if authorization_file else None,
    )
    app = CentralSystemApp(config)
    await app.start()

    entry_data = OccpEntryData(app=app, default_id_tag=entry.data.get(CONF_DEFAULT_ID_TAG))
    entry.runtime_data = entry_data

    device_registry = dr.async_get(hass)

    def _forward(event: StateChangeEvent) -> None:
        # Auf jedem Event statt nur beim ersten: die erste StateChangeEvent ist der
        # blanke WebSocket-Connect (transport.py), noch vor BootNotification --
        # vendor/model werden erst mit deren mark_boot()-Aufruf bekannt.
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **charge_point_device_info(event.charge_point_id, app.registry.get(event.charge_point_id)),
        )
        if event.charge_point_id not in entry_data.known_charge_points:
            entry_data.known_charge_points.add(event.charge_point_id)
            async_dispatcher_send(hass, signal_new_charge_point(entry.entry_id), event.charge_point_id)
        async_dispatcher_send(
            hass,
            signal_state_update(entry.entry_id, event.charge_point_id),
            event,
        )

    unsubscribe = app.query_service.subscribe(_forward)
    entry.async_on_unload(unsubscribe)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OccpConfigEntry) -> bool:
    """Stop the entry's `CentralSystemApp` and unload its platforms."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.app.stop()
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            async_unregister_services(hass)
    return unloaded
