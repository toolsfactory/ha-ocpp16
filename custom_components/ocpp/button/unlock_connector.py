"""Unlock als Button-Entity (kein REQ-0035-Vertragsbestandteil, siehe ``occp.unlock_connector``)."""

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.core.domain.commands import CommandError
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from ._base import _OcppConnectorButtonBase


class OcppUnlockConnectorButton(_OcppConnectorButtonBase):
    """Löst UnlockConnector für diesen Connector aus.

    Dashboard-idiomatische Ergänzung zum bestehenden
    ``ocpp.unlock_connector``-Service (kein REQ-0035-Vertragsbestandteil).
    """

    _attr_translation_key = "unlock_connector"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "unlock_connector")

    async def async_press(self) -> None:
        """Send UnlockConnector for this connector."""
        try:
            result = await self._entry_data.app.command_service.unlock_connector(
                self._charge_point_id, self._connector_id
            )
        except CommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        if result.status != "Unlocked":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="unlock_rejected",
                translation_placeholders={"status": result.status},
            )
