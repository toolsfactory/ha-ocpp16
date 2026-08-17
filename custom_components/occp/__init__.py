"""OCCP Home-Assistant-Layer: verdrahtet ``occp.app.CentralSystemApp`` (aus
dem Standalone-Kern, ``src/occp/``) mit Home Assistants Event-Loop, Device-
Registry und Entity-Plattformen (ADR-0008).

Kein ``homeassistant.*``-Import in ``src/occp/`` -- die gesamte HA-Anbindung
lebt ausschließlich hier unter ``custom_components/occp/`` (CLAUDE.md).
"""

from __future__ import annotations

import logging
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_send

from custom_components.occp.core.app import CentralSystemApp
from custom_components.occp.core.config import AppConfig
from custom_components.occp.core.domain.models import StateChangeEvent

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
from .runtime import OccpEntryData
from .services import async_register_services, async_unregister_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Baut ``CentralSystemApp`` auf und startet sie in ``hass.loop``
    (ADR-0008 Abschnitt 1: ``await app.start()`` genügt, kein
    ``hass.async_create_task`` -- ``start()`` selbst blockiert nicht)."""
    authorization_file = entry.data.get(CONF_AUTHORIZATION_FILE)
    config = AppConfig(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        authorization_file=Path(authorization_file) if authorization_file else None,
    )
    app = CentralSystemApp(config)
    await app.start()

    entry_data = OccpEntryData(
        app=app, default_id_tag=entry.data.get(CONF_DEFAULT_ID_TAG)
    )
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = entry_data

    def _forward(event: StateChangeEvent) -> None:
        if event.charge_point_id not in entry_data.known_charge_points:
            entry_data.known_charge_points.add(event.charge_point_id)
            async_dispatcher_send(
                hass, signal_new_charge_point(entry.entry_id), event.charge_point_id
            )
        async_dispatcher_send(
            hass,
            signal_state_update(entry.entry_id, event.charge_point_id),
            event,
        )

    unsubscribe = app.query_service.subscribe(_forward)
    entry.async_on_unload(unsubscribe)

    async_register_services(hass)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        domain_data: dict[str, OccpEntryData] = hass.data.get(DOMAIN, {})
        entry_data = domain_data.pop(entry.entry_id, None)
        if entry_data is not None:
            await entry_data.app.stop()
        if not domain_data:
            async_unregister_services(hass)
    return unloaded
