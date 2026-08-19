"""Options Flow: idTag-Autorisierungsliste und Default-idTag nachträglich ändern.

``OPTIONS_SCHEMA`` lebt hier (nicht in ``config_flow.py``), weil
``config_flow.py`` bereits ``OccpOptionsFlow`` aus diesem Modul importiert
(``OccpConfigFlow.async_get_options_flow``) -- ein Import in die
Gegenrichtung würde einen Zyklus erzeugen.
"""

from typing import Any

import voluptuous as vol

from custom_components.occp.const import CONF_AUTHORIZATION_FILE, CONF_DEFAULT_ID_TAG
from homeassistant.config_entries import ConfigFlowResult, OptionsFlow

from .validators.authorization import validate_authorization_file

OPTIONS_SCHEMA = vol.Schema(
    {
        vol.Optional(CONF_AUTHORIZATION_FILE): str,
        vol.Optional(CONF_DEFAULT_ID_TAG): str,
    }
)


class OccpOptionsFlow(OptionsFlow):
    """Options Flow: idTag-Autorisierungsliste und Default-idTag nachträglich ändern."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle the single options step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            authorization_file = user_input.get(CONF_AUTHORIZATION_FILE, "")
            if authorization_file:
                try:
                    await self.hass.async_add_executor_job(validate_authorization_file, authorization_file)
                except OSError, ValueError:
                    errors[CONF_AUTHORIZATION_FILE] = "invalid_authorization_file"
            if not errors:
                return self.async_create_entry(data=user_input)

        schema = self.add_suggested_values_to_schema(
            OPTIONS_SCHEMA, user_input if user_input is not None else self.config_entry.options
        )
        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
