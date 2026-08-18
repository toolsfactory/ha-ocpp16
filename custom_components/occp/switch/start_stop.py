"""Startet/stoppt eine Transaktion mit dem fest konfigurierten idTag (REQ-0020)."""

from typing import Any

from custom_components.occp.coordinator import OccpCoordinator
from custom_components.occp.core.domain.commands import CommandError
from custom_components.occp.runtime import OccpEntryData
from homeassistant.exceptions import HomeAssistantError

from ._base import _OccpConnectorSwitchBase


class OccpStartStopSwitch(_OccpConnectorSwitchBase):
    """Startet/stoppt eine Transaktion mit dem fest konfigurierten idTag.

    REQ-0020 (kein `idTag` je Startvorgang, siehe REQ-0020 Non-Goals).
    """

    _attr_translation_key = "start_stop"

    def __init__(
        self, coordinator: OccpCoordinator, entry_data: OccpEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "start_stop")

    @property
    def is_on(self) -> bool:
        """Return whether an active transaction exists on this connector."""
        active = self._entry_data.app.query_service.get_active_transactions(self._charge_point_id)
        return any(t.connector_id == self._connector_id for t in active)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Remote-start a transaction using the configured default idTag."""
        id_tag = self._entry_data.default_id_tag
        if not id_tag:
            raise HomeAssistantError(
                "Kein idTag für Remote-Start konfiguriert (REQ-0020) -- bitte "
                "beim Einrichten der OCCP-Integration ein idTag hinterlegen."
            )
        try:
            result = await self._entry_data.app.command_service.remote_start_transaction(
                self._charge_point_id, self._connector_id, id_tag
            )
        except CommandError as err:
            raise HomeAssistantError(str(err)) from err
        if not result.accepted:
            raise HomeAssistantError(f"Ladestation hat den Startbefehl abgelehnt (connector {self._connector_id}).")

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Remote-stop the connector's active transaction, if any."""
        active = self._entry_data.app.query_service.get_active_transactions(self._charge_point_id)
        transaction = next((t for t in active if t.connector_id == self._connector_id), None)
        if transaction is None:
            raise HomeAssistantError(f"Keine aktive Transaktion an connector {self._connector_id}.")
        try:
            result = await self._entry_data.app.command_service.remote_stop_transaction(transaction.transaction_id)
        except CommandError as err:
            raise HomeAssistantError(str(err)) from err
        if not result.accepted:
            raise HomeAssistantError(f"Ladestation hat den Stoppbefehl abgelehnt (connector {self._connector_id}).")
