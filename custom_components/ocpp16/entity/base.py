"""Gemeinsame Basis aller charge-point-/connectorbezogenen OCPP-Entities.

Push-only (``iot_class: local_push``): ``CoordinatorEntity`` verdrahtet
Lifecycle/Update-Listener automatisch; jede Instanz liest bei jedem
Coordinator-Update ihren Ausschnitt frisch aus
``QueryService``/``CommandService`` (ADR-0008 Abschnitt 2).

Bewusst kein Mixin einer Plattform-Entity-Klasse (``SensorEntity``,
``SwitchEntity``, ...) hier -- das bleibt Sache der jeweiligen Plattform, die
diese Basis zusätzlich einmischt, damit ``entity/`` selbst plattformneutral
bleibt.
"""

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.core.domain.models import ConnectionStatus
from custom_components.ocpp16.entity_utils.device import (
    charge_point_device_info,
    charge_point_identifier,
    connector_device_info,
    connector_identifier,
)
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.helpers.update_coordinator import CoordinatorEntity


def _is_charge_point_online(entry_data: Ocpp16EntryData, charge_point_id: str) -> bool:
    """Return whether `charge_point_id` is currently connected."""
    for cp in entry_data.app.query_service.get_charge_points():
        if cp.charge_point_id == charge_point_id:
            return cp.connection_status == ConnectionStatus.ONLINE
    return False


class Ocpp16ConnectorEntity(CoordinatorEntity[Ocpp16Coordinator]):
    """Gemeinsame Basis aller connectorbezogenen Sensor-/Switch-Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Ocpp16Coordinator,
        entry_data: Ocpp16EntryData,
        charge_point_id: str,
        connector_id: int,
        entity_key: str,
    ) -> None:
        """Initialize the entity for the given charge point connector."""
        super().__init__(coordinator)
        self._entry_data = entry_data
        self._charge_point_id = charge_point_id
        self._connector_id = connector_id
        self._attr_unique_id = (
            f"{connector_identifier(entry_data.entry_id, charge_point_id, connector_id)}_{entity_key}"
        )
        self._attr_device_info = connector_device_info(entry_data.entry_id, charge_point_id, connector_id)

    @property
    def available(self) -> bool:
        """Return whether the coordinator is healthy and the charge point is connected."""
        if not super().available:
            return False
        return _is_charge_point_online(self._entry_data, self._charge_point_id)


class Ocpp16ChargePointEntity(CoordinatorEntity[Ocpp16Coordinator]):
    """Gemeinsame Basis aller charge-point-weiten Sensor-/Button-Entities."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: Ocpp16Coordinator,
        entry_data: Ocpp16EntryData,
        charge_point_id: str,
        entity_key: str,
    ) -> None:
        """Initialize the entity for the given charge point."""
        super().__init__(coordinator)
        self._entry_data = entry_data
        self._charge_point_id = charge_point_id
        self._attr_unique_id = f"{charge_point_identifier(entry_data.entry_id, charge_point_id)}_{entity_key}"
        self._attr_device_info = charge_point_device_info(entry_data.entry_id, charge_point_id, None)

    @property
    def available(self) -> bool:
        """Return whether the coordinator is healthy and the charge point is connected."""
        if not super().available:
            return False
        return _is_charge_point_online(self._entry_data, self._charge_point_id)
