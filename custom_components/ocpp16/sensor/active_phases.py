"""Aktive Phasen: Anzahl + je Phase aktueller Ladestrom (kein Interop-Vertrag-Bestandteil)."""

from typing import Any

from custom_components.ocpp16.const import MEASURAND_CURRENT_IMPORT
from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.components.sensor import SensorStateClass
from homeassistant.core import callback

from ._base import _OcppConnectorSensorBase

_PHASES = ("L1", "L2", "L3")


class Ocpp16ActivePhasesSensor(_OcppConnectorSensorBase):
    """Anzahl aktuell aktiver Ladephasen, mit den Phasenströmen als Attribute.

    Kein Bestandteil des REQ-0035-Interop-Vertrags -- ergänzende Sicht auf
    dieselben ``Current.Import``-Messwerte, die auch die dynamischen
    Measurand-Sensoren (REQ-0018) je Phase anzeigen.
    """

    _attr_translation_key = "active_phases"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: Ocpp16Coordinator, entry_data: Ocpp16EntryData, charge_point_id: str, connector_id: int
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator, entry_data, charge_point_id, connector_id, "active_phases")
        self._currents = self._compute_phase_currents()

    def _compute_phase_currents(self) -> dict[str, float | None]:
        samples = self._entry_data.app.query_service.get_meter_samples(
            charge_point_id=self._charge_point_id, connector_id=self._connector_id
        )
        by_phase = {
            sample.phase: sample.value
            for sample in samples
            if sample.measurand == MEASURAND_CURRENT_IMPORT and sample.phase in _PHASES
        }
        result: dict[str, float | None] = {}
        for phase in _PHASES:
            raw = by_phase.get(phase)
            if raw is None:
                result[phase] = None
                continue
            try:
                result[phase] = float(raw)
            except ValueError:
                result[phase] = None
        return result

    @callback
    def _handle_coordinator_update(self) -> None:
        # native_value and extra_state_attributes must describe the same instant -- caching one
        # snapshot per update, instead of each property re-querying and re-filtering the mutable
        # sample list independently, keeps a single state-write internally consistent even if
        # another MeterValues event lands between property reads.
        self._currents = self._compute_phase_currents()
        super()._handle_coordinator_update()

    @property
    def native_value(self) -> int:
        """Return how many phases currently report a nonzero `Current.Import`."""
        return sum(1 for value in self._currents.values() if value is not None and value > 0)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return each phase's current reading in amperes, or `None` if that phase isn't reporting."""
        return {
            "phase_l1_a": self._currents["L1"],
            "phase_l2_a": self._currents["L2"],
            "phase_l3_a": self._currents["L3"],
        }
