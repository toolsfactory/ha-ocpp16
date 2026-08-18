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
from custom_components.occp.core.domain.authorization import StaticAuthorizationProvider
from custom_components.occp.core.domain.models import StateChangeEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG, CONF_HOST, CONF_PORT, DOMAIN, PLATFORMS
from .coordinator import OccpCoordinator
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
    authorization_path = (
        Path(entry.options[CONF_AUTHORIZATION_FILE]) if entry.options.get(CONF_AUTHORIZATION_FILE) else None
    )
    config = AppConfig(
        host=entry.data[CONF_HOST],
        port=entry.data[CONF_PORT],
        authorization_file=authorization_path,
    )
    authorization = (
        await hass.async_add_executor_job(StaticAuthorizationProvider.from_json_file, authorization_path)
        if authorization_path is not None
        else None
    )
    app = CentralSystemApp(config, authorization=authorization)
    try:
        await app.start()
    except OSError as err:
        raise ConfigEntryNotReady(
            f"Konnte den WebSocket-Server nicht auf {config.host}:{config.port} binden: {err}"
        ) from err

    coordinator = OccpCoordinator(hass, entry, app)
    entry.async_on_unload(coordinator.async_unsubscribe)

    entry_data = OccpEntryData(app=app, coordinator=coordinator, default_id_tag=entry.options.get(CONF_DEFAULT_ID_TAG))
    entry.runtime_data = entry_data

    device_registry = dr.async_get(hass)

    def _register_device(event: StateChangeEvent) -> None:
        # Auf jedem Event statt nur beim ersten: die erste StateChangeEvent ist der
        # blanke WebSocket-Connect (transport.py), noch vor BootNotification --
        # vendor/model werden erst mit deren mark_boot()-Aufruf bekannt.
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **charge_point_device_info(event.charge_point_id, app.registry.get(event.charge_point_id)),
        )

    unsubscribe_device_registration = app.query_service.subscribe(_register_device)
    entry.async_on_unload(unsubscribe_device_registration)

    # authorization_file/default_id_tag sind einmalig in CentralSystemApp/entry_data
    # eingebaut -- eine Options-Änderung braucht einen Reload, um zu wirken.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_on_options_update(hass: HomeAssistant, entry: OccpConfigEntry) -> None:
    """Reload the entry so a changed option actually takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OccpConfigEntry) -> bool:
    """Stop the entry's `CentralSystemApp` and unload its platforms."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.app.stop()
        if not hass.config_entries.async_loaded_entries(DOMAIN):
            async_unregister_services(hass)
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: OccpConfigEntry) -> bool:
    """Migrate an old config entry to the current version."""
    if entry.version > 1:
        # Downgrade from a future version -- refuse rather than corrupt data.
        return False

    if entry.version == 1 and entry.minor_version < 2:
        # authorization_file/default_id_tag zogen von entry.data nach entry.options
        # um (config-flow-Regel: nur Verbindungsdaten in entry.data).
        data = dict(entry.data)
        options = dict(entry.options)
        for key in (CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG):
            if key in data:
                options[key] = data.pop(key)
        hass.config_entries.async_update_entry(entry, data=data, options=options, minor_version=2)
        _LOGGER.debug("Migrated OCCP config entry %s to version 1.2", entry.entry_id)

    return True
