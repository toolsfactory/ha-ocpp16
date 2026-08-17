"""Switch-Plattform.

Start/Stop (REQ-0020) und Verfügbarkeit = Fähigkeit 6 des Interop-Vertrags
(REQ-0021, ADR-0009).
"""

from typing import Any

from custom_components.occp.core.domain.commands import CommandError
from custom_components.occp.core.domain.models import ConnectionStatus, QueryService, StateChangeEvent
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import signal_new_charge_point, signal_state_update
from .device import connector_device_info
from .runtime import OccpConfigEntry, OccpEntryData


async def async_setup_entry(
    hass: HomeAssistant, entry: OccpConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up switch entities for a config entry."""
    manager = _SwitchManager(hass, entry.entry_id, entry.runtime_data, async_add_entities)
    manager.async_setup()


class _SwitchManager:
    """Analog ``sensor._SensorManager``.

    Legt Switch-Entities dynamisch je Connector an, sobald ein Charge Point
    erstmals bekannt wird.
    """

    def __init__(
        self,
        hass: HomeAssistant,
        entry_id: str,
        entry_data: OccpEntryData,
        async_add_entities: AddEntitiesCallback,
    ) -> None:
        self.hass = hass
        self.entry_id = entry_id
        self.entry_data = entry_data
        self.async_add_entities = async_add_entities
        self._known_connectors: set[tuple[str, int]] = set()
        self._known_charge_points: set[str] = set()

    def async_setup(self) -> None:
        async_dispatcher_connect(self.hass, signal_new_charge_point(self.entry_id), self._async_add_charge_point)
        for snapshot in self.entry_data.app.query_service.get_charge_points():
            self._async_add_charge_point(snapshot.charge_point_id)

    @callback
    def _async_add_charge_point(self, charge_point_id: str) -> None:
        if charge_point_id in self._known_charge_points:
            return
        self._known_charge_points.add(charge_point_id)
        async_dispatcher_connect(
            self.hass,
            signal_state_update(self.entry_id, charge_point_id),
            callback(lambda event: self._handle_event(charge_point_id, event)),
        )
        self._sync_connectors(charge_point_id)

    @callback
    def _handle_event(self, charge_point_id: str, event: StateChangeEvent) -> None:
        self._sync_connectors(charge_point_id, only_connector_id=event.connector_id)

    def _sync_connectors(self, charge_point_id: str, only_connector_id: int | None = None) -> None:
        query_service = self.entry_data.app.query_service
        connector_ids = (
            [only_connector_id]
            if only_connector_id is not None
            else [c.connector_id for c in query_service.get_connectors(charge_point_id)]
        )

        new_entities: list[SwitchEntity] = []
        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008/ADR-0009: kein charge-point-weiter v1-Scope.
            key = (charge_point_id, connector_id)
            if key in self._known_connectors:
                continue
            self._known_connectors.add(key)
            new_entities.extend(
                [
                    OccpStartStopSwitch(self.entry_id, self.entry_data, charge_point_id, connector_id),
                    OccpAvailabilitySwitch(self.entry_id, self.entry_data, charge_point_id, connector_id),
                ]
            )
        if new_entities:
            self.async_add_entities(new_entities)


def _is_charge_point_online(query_service: QueryService, charge_point_id: str) -> bool:
    for cp in query_service.get_charge_points():
        if cp.charge_point_id == charge_point_id:
            return cp.connection_status == ConnectionStatus.ONLINE
    return False


class _OccpConnectorSwitchBase(SwitchEntity):
    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        entry_id: str,
        entry_data: OccpEntryData,
        charge_point_id: str,
        connector_id: int,
        entity_key: str,
    ) -> None:
        self._entry_id = entry_id
        self._entry_data = entry_data
        self._charge_point_id = charge_point_id
        self._connector_id = connector_id
        self._attr_unique_id = f"{charge_point_id}_{connector_id}_{entity_key}"
        self._attr_device_info = connector_device_info(charge_point_id, connector_id)

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                signal_state_update(self._entry_id, self._charge_point_id),
                self._async_handle_event,
            )
        )

    async def _async_handle_event(self, event: StateChangeEvent) -> None:
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        return _is_charge_point_online(self._entry_data.app.query_service, self._charge_point_id)


class OccpStartStopSwitch(_OccpConnectorSwitchBase):
    """Startet/stoppt eine Transaktion mit dem fest konfigurierten idTag.

    REQ-0020 (kein `idTag` je Startvorgang, siehe REQ-0020 Non-Goals).
    """

    _attr_translation_key = "start_stop"

    def __init__(self, entry_id: str, entry_data: OccpEntryData, charge_point_id: str, connector_id: int) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, "start_stop")

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


class OccpAvailabilitySwitch(_OccpConnectorSwitchBase):
    """Fähigkeit 6 des Interop-Vertrags (REQ-0021).

    Dieselbe Entity, keine zweite parallele Interop-Entity, siehe REQ-0021
    "Entscheidung".
    """

    _attr_translation_key = "availability"

    def __init__(self, entry_id: str, entry_data: OccpEntryData, charge_point_id: str, connector_id: int) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(entry_id, entry_data, charge_point_id, connector_id, "availability")
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
            raise HomeAssistantError(str(err)) from err
        self._last_change_status = result.status
        if result.status == "Rejected":
            raise HomeAssistantError(
                f"Ladestation hat die Verfügbarkeitsänderung abgelehnt (connector {self._connector_id})."
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
