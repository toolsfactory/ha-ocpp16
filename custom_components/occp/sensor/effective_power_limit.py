"""Wirksame Leistungsgrenze über ``GetCompositeSchedule`` (Fähigkeit 5, REQ-0035 AC4)."""

import asyncio
import logging
from typing import TYPE_CHECKING

from custom_components.occp.coordinator import OccpCoordinator
from custom_components.occp.runtime import OccpEntryData
from custom_components.occp.utils import interop
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.const import UnitOfPower
from homeassistant.core import callback

from ._base import _OccpConnectorSensorBase

_LOGGER = logging.getLogger(__name__)


class OccpEffectivePowerLimitSensor(_OccpConnectorSensorBase):
    """Wirksame Leistungsgrenze über ``GetCompositeSchedule``.

    Fähigkeit 5 des Interop-Vertrags (REQ-0035 AC4) -- erfordert einen
    Central-System-initiierten Aufruf, deshalb asynchron im
    Dispatcher-Callback aktualisiert und zwischengespeichert (ADR-0010).
    """

    _attr_translation_key = "effective_power_limit_w"
    _attr_device_class = SensorDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT

    def __init__(
        self, coordinator: OccpCoordinator, entry_data: OccpEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "effective_power_limit_w")
        self._value: float | None = None
        self._refresh_lock = asyncio.Lock()
        self._refresh_pending = False

    @callback
    def _handle_coordinator_update(self) -> None:
        event = self.coordinator.data
        if event is not None and (
            event.charge_point_id != self._charge_point_id
            or (event.connector_id is not None and event.connector_id != self._connector_id)
        ):
            # Weder für unseren Charge Point noch (falls Connector-spezifisch)
            # für unseren Connector -- ein GetCompositeSchedule-Aufruf hier
            # wäre nur unnötiger Central-System-initiierter Traffic. Ohne die
            # charge_point_id-Prüfung würden mehrere Charge Points an einer
            # Instanz mit identischer Connector-Nummerierung sich gegenseitig
            # zu unnötigen Abfragen triggern.
            return
        if self._refresh_lock.locked():
            # Ein Refresh läuft bereits -- statt eines weiteren parallelen
            # GetCompositeSchedule-Aufrufs (unnötiger Central-System-initiierter
            # Traffic bei einem Event-Burst) merken wir vor, dass nach dem
            # laufenden Versuch noch einmal aufgefrischt werden muss.
            self._refresh_pending = True
            return
        if TYPE_CHECKING:
            assert self.coordinator.config_entry is not None
        self.coordinator.config_entry.async_create_background_task(
            self.hass,
            self._async_refresh_power_limit(),
            f"occp_effective_power_limit_{self._charge_point_id}_{self._connector_id}",
        )

    async def _async_refresh_power_limit(self) -> None:
        async with self._refresh_lock:
            while True:
                self._refresh_pending = False
                try:
                    self._value = await interop.get_effective_power_limit_w(
                        self._entry_data.app.command_service,
                        self._charge_point_id,
                        self._connector_id,
                    )
                except Exception:
                    # Central-System-initiierter Aufruf kann jederzeit fehlschlagen
                    # (z. B. Charge Point trennt gerade die Verbindung) -- ein
                    # einzelner fehlgeschlagener GetCompositeSchedule-Versuch darf
                    # nicht den gesamten Coordinator-Listener (und damit andere
                    # Entities desselben Updates) zum Absturz bringen.
                    _LOGGER.debug(
                        "GetCompositeSchedule für %s/%s fehlgeschlagen, Wert bleibt unverändert.",
                        self._charge_point_id,
                        self._connector_id,
                        exc_info=True,
                    )
                self.async_write_ha_state()
                if not self._refresh_pending:
                    break

    @property
    def native_value(self) -> float | None:
        """Return the connector's last fetched effective power limit in watts."""
        return self._value
