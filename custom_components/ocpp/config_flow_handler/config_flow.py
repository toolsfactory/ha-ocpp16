"""Config Flow für OCPP (REQ-0016, REQ-0022, ADR-0008 Abschnitt 4).

Einstufiger ``user``-Schritt: Listen-Adresse/-Port für den WebSocket-Endpunkt
landen in ``entry.data`` (für den Verbindungsaufbau nötig). Der optionale
Pfad zur statischen idTag-Autorisierungsliste (REQ-0005) und ein für
RemoteStartTransaction fest konfiguriertes idTag (REQ-0020) landen in
``entry.options`` -- beides über den Options-Flow nachträglich änderbar, ohne
den Entry neu anzulegen. ``unique_id`` ist eine zufällige UUID (Host/Port
sind laut Projektregel keine zulässige unique_id-Quelle); ein Duplikat mit
derselben Host/Port-Kombination wird stattdessen explizit über
``_host_port_already_configured`` abgefangen.

Ein optionales TLS-Zertifikat/Schlüssel-Paar für direktes ``wss://`` (Phase 5, kein
Reverse Proxy nötig) landet ebenfalls in ``entry.data`` -- verbindungskritisch wie
Host/Port, daher auch im ``reconfigure``-Schritt änderbar statt nur im Options-Flow.
Beide Felder leer lassen behält ``ws://`` bei; nur eines von beiden ist ein Formularfehler.
"""

import socket
import ssl
from typing import Any
from uuid import uuid4

import voluptuous as vol

from custom_components.ocpp.const import (
    CONF_AUTHORIZATION_FILE,
    CONF_CERTIFICATE_PATH,
    CONF_DEFAULT_ID_TAG,
    CONF_HOST,
    CONF_MAX_POWER_LIMIT_W,
    CONF_PORT,
    CONF_PRIVATE_KEY_PATH,
    DEFAULT_HOST,
    DEFAULT_MAX_POWER_LIMIT_W,
    DEFAULT_PORT,
    DOMAIN,
)
from custom_components.ocpp.core.domain.authorization import IdTagStatus
from homeassistant.config_entries import ConfigEntry, ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.core import HomeAssistant

from .options_flow import OPTIONS_SCHEMA, OcppOptionsFlow
from .validators.authorization import validate_authorization_file
from .validators.tls import validate_tls_certificate


def _try_bind_port(host: str, port: int) -> None:
    """Kurzzeitiger Testbind (REQ-0016 AC2, ADR-0008 Abschnitt 4).

    Läuft über ``hass.async_add_executor_job`` (synchroner Sockettest, nicht
    Event-Loop-blockierend). Bewusste, dokumentierte Einschränkung laut
    ADR-0008: reine Momentaufnahme, kein Schutz vor einem Race zwischen
    Testbind und dem tatsächlichen ``CentralSystemApp.start()``.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))


async def _validate_tls_pair(hass: HomeAssistant, certificate_path: str, private_key_path: str) -> str | None:
    """Validate an optional TLS certificate/private-key pair (Phase 5, direct `wss://`).

    Returns a translation key for a form error, or `None` if the pair loads cleanly or
    both fields are empty -- `wss://` stays opt-in, `ws://` is the unchanged default.
    """
    if bool(certificate_path) != bool(private_key_path):
        return "tls_incomplete_pair"
    if not certificate_path:
        return None
    try:
        await hass.async_add_executor_job(validate_tls_certificate, certificate_path, private_key_path)
    except OSError, ssl.SSLError:
        return "tls_certificate_invalid"
    return None


class OcppConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow für das OCPP Central System."""

    VERSION = 1
    MINOR_VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the single `user` setup step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            if self._host_port_already_configured(host, port):
                return self.async_abort(reason="already_configured")

            authorization_file = user_input.get(CONF_AUTHORIZATION_FILE, "")
            default_id_tag = user_input.get(CONF_DEFAULT_ID_TAG, "")
            certificate_path = user_input.get(CONF_CERTIFICATE_PATH, "")
            private_key_path = user_input.get(CONF_PRIVATE_KEY_PATH, "")
            try:
                await self.hass.async_add_executor_job(_try_bind_port, host, port)
            except OSError:
                errors["port"] = "port_in_use"
            if not errors and authorization_file:
                try:
                    provider = await self.hass.async_add_executor_job(validate_authorization_file, authorization_file)
                except OSError, ValueError:
                    errors[CONF_AUTHORIZATION_FILE] = "invalid_authorization_file"
                else:
                    if default_id_tag and provider.authorize(default_id_tag).status is not IdTagStatus.ACCEPTED:
                        errors[CONF_DEFAULT_ID_TAG] = "default_id_tag_not_authorized"
            elif not errors and default_id_tag:
                # Ein Default-idTag (REQ-0020) ohne Autorisierungsdatei würde nie akzeptiert
                # (leere Liste lehnt alles ab, siehe StaticAuthorizationProvider.authorize) --
                # nur ein akzeptierter Eintrag darf als Default gespeichert werden.
                errors[CONF_DEFAULT_ID_TAG] = "default_id_tag_not_authorized"
            if not errors:
                tls_error = await _validate_tls_pair(self.hass, certificate_path, private_key_path)
                if tls_error:
                    errors[CONF_CERTIFICATE_PATH] = tls_error
            if not errors:
                await self.async_set_unique_id(str(uuid4()))
                return self.async_create_entry(
                    title=f"OCPP ({host}:{port})",
                    data={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_CERTIFICATE_PATH: certificate_path,
                        CONF_PRIVATE_KEY_PATH: private_key_path,
                    },
                    options={
                        CONF_AUTHORIZATION_FILE: authorization_file,
                        CONF_DEFAULT_ID_TAG: user_input.get(CONF_DEFAULT_ID_TAG, ""),
                        CONF_MAX_POWER_LIMIT_W: user_input.get(CONF_MAX_POWER_LIMIT_W, DEFAULT_MAX_POWER_LIMIT_W),
                    },
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(CONF_CERTIFICATE_PATH): str,
                vol.Optional(CONF_PRIVATE_KEY_PATH): str,
            }
        ).extend(OPTIONS_SCHEMA.schema)
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    def _host_port_already_configured(self, host: str, port: int, *, exclude_entry_id: str | None = None) -> bool:
        """Return whether another entry already binds the same host/port.

        Ersetzt den früheren ``_abort_if_unique_id_configured()``-Duplikatscheck,
        der auf Host:Port als ``unique_id`` beruhte -- seit ``unique_id`` eine
        zufällige UUID ist (Projektregel: nie Host/Port als unique_id), muss
        das Duplikat explizit über die Entry-Daten geprüft werden. ``exclude_entry_id``
        lässt beim Reconfigure-Flow den zu bearbeitenden Eintrag selbst zu -- sonst würde
        ein unverändertes Speichern immer als Duplikat abgelehnt.
        """
        return any(
            entry.entry_id != exclude_entry_id
            and entry.data.get(CONF_HOST) == host
            and entry.data.get(CONF_PORT) == port
            for entry in self._async_current_entries(include_ignore=False)
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Change an existing entry's host/port without deleting and re-adding it.

        REQ-0005/REQ-0020-Optionen (Autorisierungsdatei, Default-idTag) bleiben bewusst
        außen vor -- die ändert der bereits vorhandene Options-Flow. ``unique_id`` ist
        eine zufällige UUID, unabhängig von Host/Port (Projektregel), daher keine
        Versionierung/Migration nötig -- nur die Werte in ``entry.data`` ändern sich,
        nicht deren Form.
        """
        errors: dict[str, str] = {}
        reconfigure_entry = self._get_reconfigure_entry()

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]
            certificate_path = user_input.get(CONF_CERTIFICATE_PATH, "")
            private_key_path = user_input.get(CONF_PRIVATE_KEY_PATH, "")

            if self._host_port_already_configured(host, port, exclude_entry_id=reconfigure_entry.entry_id):
                return self.async_abort(reason="already_configured")

            try:
                await self.hass.async_add_executor_job(_try_bind_port, host, port)
            except OSError:
                errors["port"] = "port_in_use"

            if not errors:
                tls_error = await _validate_tls_pair(self.hass, certificate_path, private_key_path)
                if tls_error:
                    errors[CONF_CERTIFICATE_PATH] = tls_error

            if not errors:
                return self.async_update_reload_and_abort(
                    reconfigure_entry,
                    data_updates={
                        CONF_HOST: host,
                        CONF_PORT: port,
                        CONF_CERTIFICATE_PATH: certificate_path,
                        CONF_PRIVATE_KEY_PATH: private_key_path,
                    },
                )

        schema = self.add_suggested_values_to_schema(
            vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_PORT): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                    vol.Optional(CONF_CERTIFICATE_PATH): str,
                    vol.Optional(CONF_PRIVATE_KEY_PATH): str,
                }
            ),
            user_input if user_input is not None else reconfigure_entry.data,
        )
        return self.async_show_form(step_id="reconfigure", data_schema=schema, errors=errors)

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Return the options flow handler for this config entry."""
        return OcppOptionsFlow()
