"""Options Flow: idTag-Autorisierungsliste und Default-idTag nachträglich ändern.

``OPTIONS_SCHEMA`` lebt hier (nicht in ``config_flow.py``), weil
``config_flow.py`` bereits ``OcppOptionsFlow`` aus diesem Modul importiert
(``OcppConfigFlow.async_get_options_flow``) -- ein Import in die
Gegenrichtung würde einen Zyklus erzeugen.
"""

from typing import Any

import voluptuous as vol

from custom_components.ocpp.const import (
    CONF_AUTHORIZATION_FILE,
    CONF_DEFAULT_ID_TAG,
    CONF_MAX_POWER_LIMIT_W,
    DEFAULT_MAX_POWER_LIMIT_W,
)
from custom_components.ocpp.core.domain.authorization import IdTagStatus
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

from .validators.authorization import validate_authorization_file

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AUTHORIZATION_FILE): str,
        vol.Optional(CONF_DEFAULT_ID_TAG): str,
        vol.Optional(CONF_MAX_POWER_LIMIT_W, default=DEFAULT_MAX_POWER_LIMIT_W): vol.All(
            vol.Coerce(float), vol.Range(min=0.01)
        ),
    }
)


class OcppOptionsFlow(OptionsFlow):
    """Options Flow: idTag-Autorisierungsliste und Default-idTag nachträglich ändern."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the single options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            authorization_file = user_input.get(CONF_AUTHORIZATION_FILE, "")
            default_id_tag = user_input.get(CONF_DEFAULT_ID_TAG, "")
            if authorization_file:
                try:
                    provider = await self.hass.async_add_executor_job(validate_authorization_file, authorization_file)
                except OSError, ValueError:
                    errors[CONF_AUTHORIZATION_FILE] = "invalid_authorization_file"
                else:
                    if default_id_tag and provider.authorize(default_id_tag).status is not IdTagStatus.ACCEPTED:
                        errors[CONF_DEFAULT_ID_TAG] = "default_id_tag_not_authorized"
            elif default_id_tag:
                # Ein Default-idTag (REQ-0020) ohne Autorisierungsdatei würde nie akzeptiert
                # (leere Liste lehnt alles ab, siehe StaticAuthorizationProvider.authorize) --
                # nur ein akzeptierter Eintrag darf als Default gespeichert werden.
                errors[CONF_DEFAULT_ID_TAG] = "default_id_tag_not_authorized"
            if not errors:
                return self.async_create_entry(data=user_input)

        schema = self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, user_input if user_input is not None else self.config_entry.options
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
