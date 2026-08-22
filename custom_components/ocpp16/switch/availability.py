"""Fähigkeit 6 des Interop-Vertrags: Verfügbarkeit (REQ-0021, ADR-0009)."""

from typing import Any

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.core.domain.commands import CommandError
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.exceptions import HomeAssistantError

from ._base import _OcppConnectorSwitchBase


class Ocpp16AvailabilitySwitch(_OcppConnectorSwitchBase):
    """Fähigkeit 6 des Interop-Vertrags (REQ-0021).

    Dieselbe Entity, keine zweite parallele Interop-Entity, siehe REQ-0021
    "Entscheidung".
    """

    _attr_translation_key = "availability"

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "availability")
        self._last_change_status: str | None = None

    @property
    def _connector_snapshot(self):
        return self._entry_data.app.query_service.get_connector(self._charge_point_id, self._connector_id)

    @property
    def is_on(self) -> bool | None:
        """Return whether the connector is operative (available for charging)."""
        snapshot = self._connector_snapshot
        if snapshot is None:
            return None
        # Fähigkeit 6 (interop-contract.md): on = freigegeben, off = gesperrt.
        return snapshot.status != "Unavailable"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the status of the last ChangeAvailability call."""
        return {
            "last_change_status": self._last_change_status,
            "change_pending": self._last_change_status == "Scheduled",
        }

    async def _async_change(self, availability_type: str) -> None:
        try:
            result = await self._entry_data.app.command_service.change_availability(
                self._charge_point_id, self._connector_id, availability_type
            )
        except CommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        self._last_change_status = result.status
        if result.status == "Rejected":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="availability_change_rejected",
                translation_placeholders={"connector_id": str(self._connector_id)},
            )
        # REQ-0021 AC2: "Scheduled" wird NICHT als sofortige Zustandsänderung
        # behandelt -- der tatsächliche Zustand ergibt sich weiterhin
        # ausschließlich aus der nächsten StatusNotification (ADR-0009).
        self.async_write_ha_state()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send ChangeAvailability(Operative) for this connector."""
        await self._async_change("Operative")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send ChangeAvailability(Inoperative) for this connector."""
        await self._async_change("Inoperative")
