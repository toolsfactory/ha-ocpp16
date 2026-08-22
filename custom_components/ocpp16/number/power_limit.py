"""Dashboard-idiomatisches Setzen/Löschen der Leistungsgrenze (Fähigkeit 3/4, kein eigener Vertragsbestandteil)."""

from custom_components.ocpp16.const import DOMAIN
from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.core.domain.commands import CommandError
from custom_components.ocpp16.runtime import Ocpp16EntryData
from custom_components.ocpp16.utils import interop
from homeassistant.components.number import NumberDeviceClass, NumberMode, RestoreNumber
from homeassistant.const import UnitOfPower
from homeassistant.exceptions import HomeAssistantError

from ._base import _OcppConnectorNumberBase


class Ocpp16PowerLimitNumber(_OcppConnectorNumberBase, RestoreNumber):
    """Setzt/löscht die Leistungsgrenze über dieselben Fähigkeit-3/4-Funktionen wie die Services.

    ``native_value`` ist optimistisch (letzter erfolgreich gesetzter/gelöschter Wert), kein
    eigener ``GetCompositeSchedule``-Live-Refresh -- das bleibt Aufgabe des dedizierten
    ``effective_power_limit_w``-Sensors (mit dem Entwickler bestätigt: kein doppelter
    Central-System-initiierter Traffic für dieselbe Information). Über einen HA-Neustart hinweg
    wird derselbe zuletzt gesetzte Wert per ``RestoreNumber`` wiederhergestellt statt erneut
    ``unknown`` zu zeigen (Entscheidung 2026-08-21, siehe DECISIONS.md) -- das ist weiterhin nur
    der zuletzt *gesetzte* Sollwert, keine erneute Bestätigung des tatsächlichen Ist-Zustands.
    """

    _attr_translation_key = "power_limit_w"
    _attr_device_class = NumberDeviceClass.POWER
    _attr_native_unit_of_measurement = UnitOfPower.WATT
    _attr_native_min_value = 0
    _attr_mode = NumberMode.BOX

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "power_limit_w")
        self._attr_native_max_value = entry_data.max_power_limit_w
        self._value: float | None = None

    async def async_added_to_hass(self) -> None:
        """Restore the last set value across a HA restart, if one was ever recorded."""
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._value = last_data.native_value

    @property
    def native_value(self) -> float | None:
        """Return the last successfully set/cleared power limit, or `None` if never set."""
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
