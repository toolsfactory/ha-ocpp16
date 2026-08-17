"""Config Flow für OCCP (REQ-0016, REQ-0022, ADR-0008 Abschnitt 4).

Einstufiger ``user``-Schritt: Listen-Adresse/-Port für den WebSocket-
Endpunkt, optional der Pfad zur statischen idTag-Autorisierungsliste
(REQ-0005) und ein für RemoteStartTransaction fest konfiguriertes idTag
(REQ-0020, siehe ``const.py``-Kommentar zu ``CONF_DEFAULT_ID_TAG``).
"""

from __future__ import annotations

import socket
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult

from .const import (
    CONF_AUTHORIZATION_FILE,
    CONF_DEFAULT_ID_TAG,
    CONF_HOST,
    CONF_PORT,
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOMAIN,
)


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


class OccpConfigFlow(ConfigFlow, domain=DOMAIN):
    """Config Flow für das OCCP Central System."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOST]
            port = user_input[CONF_PORT]

            await self.async_set_unique_id(f"{host}:{port}")
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(_try_bind_port, host, port)
            except OSError:
                errors["port"] = "port_in_use"
            else:
                return self.async_create_entry(
                    title=f"OCCP ({host}:{port})", data=user_input
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_PORT, default=DEFAULT_PORT): vol.All(
                    vol.Coerce(int), vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_AUTHORIZATION_FILE): str,
                vol.Optional(CONF_DEFAULT_ID_TAG): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)
