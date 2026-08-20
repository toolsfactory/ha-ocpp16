"""Soft-Reset als Button-Entity (kein REQ-0035-Vertragsbestandteil, siehe ``occp.reset``)."""

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.core.domain.commands import CommandError
from custom_components.ocpp.runtime import OcppEntryData
from homeassistant.const import EntityCategory
from homeassistant.exceptions import HomeAssistantError

from ._base import _OcppChargePointButtonBase


class OcppResetButton(_OcppChargePointButtonBase):
    """Löst einen Soft-Reset aus (Hard-Reset bleibt dem ``ocpp.reset``-Service vorbehalten).

    Dashboard-idiomatische Ergänzung zum bestehenden ``ocpp.reset``-Service
    (kein REQ-0035-Vertragsbestandteil) -- ein Button-Press kennt keinen
    Parameter, daher fest auf "Soft" begrenzt (mit dem Entwickler bestätigt).
    """

    _attr_translation_key = "reset"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str) -> None:
        """Initialize the entity for the given charge point."""
        super().__init__(coordinator, entry_data, charge_point_id, "reset")

    async def async_press(self) -> None:
        """Send a Soft Reset to the charge point."""
        try:
            result = await self._entry_data.app.command_service.reset(self._charge_point_id, "Soft")
        except CommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        if not result.accepted:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key="reset_rejected")
