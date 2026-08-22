"""Shared entity-discovery manager for platforms whose entities appear as OCPP reports connectors.

Per the push model in ADR-0008 Abschnitt 2. Every platform's ``__init__.py`` used to hand-roll its
own near-identical `_<Platform>Manager` --
coordinator listener registration, initial connector sync, `_known_connectors` tracking, and a
per-connector entity factory call. The only genuine divergence between platforms is which entities
to create (via the factories below) and whether a platform has charge-point-wide entities at all.
"""

from collections.abc import Callable

from custom_components.ocpp16.coordinator import Ocpp16Coordinator
from custom_components.ocpp16.runtime import Ocpp16EntryData
from homeassistant.core import CALLBACK_TYPE, callback
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddEntitiesCallback

ConnectorEntityFactory = Callable[[Ocpp16Coordinator, Ocpp16EntryData, str, int], list[Entity]]
ChargePointEntityFactory = Callable[[Ocpp16Coordinator, Ocpp16EntryData, str], list[Entity]]


class DynamicPlatformManager:
    """Setup-time helper that creates entities dynamically as connectors/charge points appear.

    Not an entity itself -- a lean, push-based alternative to HA discovery callbacks, reacting to
    `Ocpp16Coordinator` updates instead of its own dispatcher signals.
    """

    def __init__(
        self,
        entry_data: Ocpp16EntryData,
        async_add_entities: AddEntitiesCallback,
        connector_entity_factory: ConnectorEntityFactory,
        charge_point_entity_factory: ChargePointEntityFactory | None = None,
        extra_connector_entity_factory: ConnectorEntityFactory | None = None,
    ) -> None:
        """Store the factories a platform supplies.

        `charge_point_entity_factory` is only called (and only tracked at all) for platforms that
        have charge-point-wide entities. `extra_connector_entity_factory` is called for every
        connector on every sync, known or not -- for sensor's measurand sub-discovery, where new
        measurands can appear on an already-known connector.
        """
        self.entry_data = entry_data
        self.coordinator = entry_data.coordinator
        self.async_add_entities = async_add_entities
        self._connector_entity_factory = connector_entity_factory
        self._charge_point_entity_factory = charge_point_entity_factory
        self._extra_connector_entity_factory = extra_connector_entity_factory
        self._known_connectors: set[tuple[str, int]] = set()
        self._known_charge_points: set[str] | None = set() if charge_point_entity_factory else None

    def async_setup(self) -> CALLBACK_TYPE:
        """Start listening and sync already-known charge points. Returns the coordinator unsubscribe callable."""
        remove_listener = self.coordinator.async_add_listener(self._handle_coordinator_update)
        # Race zwischen app.start() und Plattform-Forward abdecken (ADR-0008):
        # bereits bekannte Charge Points direkt beim Plattform-Setup aufnehmen.
        for snapshot in self.entry_data.app.query_service.get_charge_points():
            self._sync_connectors(snapshot.charge_point_id)
        return remove_listener

    @callback
    def _handle_coordinator_update(self) -> None:
        event = self.coordinator.data
        if event is None:
            return
        self._sync_connectors(event.charge_point_id, only_connector_id=event.connector_id)

    def _sync_connectors(self, charge_point_id: str, only_connector_id: int | None = None) -> None:
        query_service = self.entry_data.app.query_service
        if only_connector_id is not None:
            connector_ids = [only_connector_id]
        else:
            connector_ids = [c.connector_id for c in query_service.get_connectors(charge_point_id)]

        new_entities: list[Entity] = []
        if (
            self._charge_point_entity_factory is not None
            and self._known_charge_points is not None
            and charge_point_id not in self._known_charge_points
        ):
            self._known_charge_points.add(charge_point_id)
            new_entities.extend(self._charge_point_entity_factory(self.coordinator, self.entry_data, charge_point_id))

        for connector_id in connector_ids:
            if connector_id < 1:
                continue  # ADR-0008: connectorId 0 hat kein eigenes Sub-Device.
            key = (charge_point_id, connector_id)
            if key not in self._known_connectors:
                self._known_connectors.add(key)
                new_entities.extend(
                    self._connector_entity_factory(self.coordinator, self.entry_data, charge_point_id, connector_id)
                )
            if self._extra_connector_entity_factory is not None:
                new_entities.extend(
                    self._extra_connector_entity_factory(
                        self.coordinator, self.entry_data, charge_point_id, connector_id
                    )
                )

        if new_entities:
            self.async_add_entities(new_entities)
