"""OCPP Home-Assistant-Layer.

Verdrahtet ``ocpp.app.CentralSystemApp`` (aus dem Standalone-Kern,
``src/ocpp/``) mit Home Assistants Event-Loop, Device-Registry und
Entity-Plattformen (ADR-0008).

Kein ``homeassistant.*``-Import in ``src/ocpp/`` -- die gesamte HA-Anbindung
lebt ausschließlich hier unter ``custom_components/ocpp/`` (CLAUDE.md).
"""

import logging
from pathlib import Path

from custom_components.ocpp.core.app import CentralSystemApp
from custom_components.ocpp.core.config import AppConfig
from custom_components.ocpp.core.domain.authorization import StaticAuthorizationProvider
from custom_components.ocpp.core.domain.models import StateChangeEvent
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryError, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_AUTHORIZATION_FILE,
    CONF_DEFAULT_ID_TAG,
    CONF_HOST,
    CONF_MAX_POWER_LIMIT_W,
    CONF_PORT,
    DEFAULT_MAX_POWER_LIMIT_W,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import OcppCoordinator
from .entity_utils.device import charge_point_device_info
from .runtime import OcppConfigEntry, OcppEntryData
from .service_actions import async_register_services

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the REQ-0035 services once, independent of config entry count."""
    async_register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: OcppConfigEntry) -> bool:
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
    if authorization_path is not None:
        try:
            authorization = await hass.async_add_executor_job(
                StaticAuthorizationProvider.from_json_file, authorization_path
            )
        except (OSError, ValueError) as err:
            # Der Options-Flow validiert dieselbe Datei beim Speichern (siehe
            # config_flow_handler/validators/authorization.py) -- dieser Zweig
            # greift, wenn die Datei danach entfernt/beschädigt wurde. Kein
            # ConfigEntryNotReady: ein erneuter Versuch ohne Eingreifen des
            # Nutzers würde denselben Fehler wiederholen. Pfad/OS-Fehlertext nur auf
            # Debug-Level -- die Nutzer-sichtbare Meldung bleibt übersetzt und generisch.
            _LOGGER.debug("Authorization file '%s' could not be loaded: %s", authorization_path, err, exc_info=True)
            raise ConfigEntryError(
                translation_domain=DOMAIN,
                translation_key="authorization_file_unreadable",
                translation_placeholders={"path": str(authorization_path)},
            ) from err
    else:
        authorization = None
    app = CentralSystemApp(config, authorization=authorization)
    try:
        await app.start()
    except OSError as err:
        _LOGGER.debug("Could not bind %s:%s: %s", config.host, config.port, err, exc_info=True)
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="bind_failed",
            translation_placeholders={"host": config.host, "port": str(config.port)},
        ) from err

    device_registry = dr.async_get(hass)

    def _register_device(event: StateChangeEvent) -> None:
        # Auf jedem Event statt nur beim ersten: die erste StateChangeEvent ist der
        # blanke WebSocket-Connect (transport.py), noch vor BootNotification --
        # vendor/model werden erst mit deren mark_boot()-Aufruf bekannt.
        device_registry.async_get_or_create(
            config_entry_id=entry.entry_id,
            **charge_point_device_info(entry.entry_id, event.charge_point_id, app.registry.get(event.charge_point_id)),
        )

    # Muss VOR dem Coordinator abonnieren: der EventBus ruft Listener in
    # Subscription-Reihenfolge auf, und der Coordinator triggert innerhalb
    # desselben synchronen Aufrufs (DataUpdateCoordinator.async_set_updated_data)
    # bereits Sensor-/Switch-Manager, deren Connector-Devices per via_device auf
    # das hier erstellte Charge-Point-Device zeigen -- andernfalls existiert das
    # beim ersten Event noch nicht.
    unsubscribe_device_registration = app.query_service.subscribe(_register_device)
    entry.async_on_unload(unsubscribe_device_registration)

    coordinator = OcppCoordinator(hass, entry, app)
    entry.async_on_unload(coordinator.async_unsubscribe)

    entry_data = OcppEntryData(
        app=app,
        coordinator=coordinator,
        default_id_tag=entry.options.get(CONF_DEFAULT_ID_TAG),
        max_power_limit_w=entry.options.get(CONF_MAX_POWER_LIMIT_W, DEFAULT_MAX_POWER_LIMIT_W),
        entry_id=entry.entry_id,
    )
    entry.runtime_data = entry_data

    # authorization_file/default_id_tag sind einmalig in CentralSystemApp/entry_data
    # eingebaut -- eine Options-Änderung braucht einen Reload, um zu wirken.
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options_update))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_reload_on_options_update(hass: HomeAssistant, entry: OcppConfigEntry) -> None:
    """Reload the entry so a changed option actually takes effect."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: OcppConfigEntry) -> bool:
    """Stop the entry's `CentralSystemApp` and unload its platforms.

    Services registered in ``async_setup()`` stay registered for the integration's lifetime --
    ``async_setup()`` runs once per HA startup, not on every entry (re)load, so unregistering them
    here would leave every OCPP service missing until the next full HA restart.
    """
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        await entry.runtime_data.app.stop()
    return unloaded


async def async_migrate_entry(hass: HomeAssistant, entry: OcppConfigEntry) -> bool:
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
        _LOGGER.debug("Migrated OCPP config entry %s to version 1.2", entry.entry_id)

    return True
