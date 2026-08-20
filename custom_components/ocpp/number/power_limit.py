"""Dashboard-idiomatisches Setzen/Löschen der Leistungsgrenze (Fähigkeit 3/4, kein eigener Vertragsbestandteil)."""

from custom_components.ocpp.const import DOMAIN
from custom_components.ocpp.coordinator import OcppCoordinator
from custom_components.ocpp.core.domain.commands import CommandError
from custom_components.ocpp.runtime import OcppEntryData
from custom_components.ocpp.utils import interop
from homeassistant.components.number import NumberDeviceClass, NumberMode
from homeassistant.const import UnitOfPower
from homeassistant.exceptions import HomeAssistantError

from ._base import _OcppConnectorNumberBase


class OcppPowerLimitNumber(_OcppConnectorNumberBase):
    """Setzt/löscht die Leistungsgrenze über dieselben Fähigkeit-3/4-Funktionen wie die Services.

    ``native_value`` ist optimistisch (letzter erfolgreich gesetzter/gelöschter Wert), kein
    eigener ``GetCompositeSchedule``-Live-Refresh -- das bleibt Aufgabe des dedizierten
    ``effective_power_limit_w``-Sensors (mit dem Entwickler bestätigt: kein doppelter
    Central-System-initiierter Traffic für dieselbe Information).
    """

    _attr_translation_key = "power_limit_w"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: OcppCoordinator, entry_data: OcppEntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "power_limit_w")
        self._attr_native_max_value = entry_data.max_power_limit_w
        self._value: float | None = None

    @property
    def native_value(self) -> float | None:
        """Return the last successfully set/cleared power limit, or `None` if never set this session."""
        return self._value

    async def async_set_native_value(self, value: float) -> None:
        """Set the power limit, or clear it if `value` is `0` (the "no limit" sentinel)."""
        command_service = self._entry_data.app.command_service
        try:
            if value == 0:
                result = await interop.clear_power_limit(command_service, self._charge_point_id, self._connector_id)
            else:
                result = await interop.set_power_limit(
                    command_service, self._charge_point_id, self._connector_id, value, phases=None
                )
        except CommandError as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_rejected",
                translation_placeholders={"error": str(err)},
            ) from err
        if result["status"] != "accepted":
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="power_limit_rejected",
                translation_placeholders={"status": result["status"]},
            )
        self._value = value
        self.async_write_ha_state()
