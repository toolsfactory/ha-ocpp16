"""Reset filter button for occp."""

from custom_components.occp.api import OccpApiClientError
from custom_components.occp.const import DOMAIN
from custom_components.occp.entity import OccpEntity
from homeassistant.components.button import ButtonDeviceClass, ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

ENTITY_DESCRIPTIONS: tuple[ButtonEntityDescription, ...] = (
    ButtonEntityDescription(
        key="reset_filter",
        translation_key="reset_filter",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
    ),
)


class OccpButton(ButtonEntity, OccpEntity):
    """Button that resets the device's filter timer."""

    async def async_press(self) -> None:
        """Reset the filter timer on the device."""
        client = self.coordinator.config_entry.runtime_data.client
        try:
            await client.async_reset_filter()
        except OccpApiClientError as exception:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reset_filter_failed",
            ) from exception

        await self.coordinator.async_request_refresh()
