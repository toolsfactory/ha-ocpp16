"""``QueryService``-Implementierung (REQ-0011): lesende Facade über Registry,
Connector- und Transaktionszustand, plus Change-Notification.

Implementiert strukturell das in ``docs/architecture/interfaces.md``
(ADR-0003, seit der Ergänzung 2026-08-15 inklusive ``get_connectors`` und
``get_meter_samples``) verbindliche ``QueryService``-Protocol. Beide
Methoden wurden ursprünglich als OCCP-interne Erweiterung eingeführt (für
die Konsole, REQ-0032/REQ-0033) und sind seit der genannten ADR-0003-
Ergänzung formal Bestandteil des Protocols — u. a. weil der künftige
HA-Layer (REQ-0017/REQ-0018) dieselbe Statusübersicht benötigt.
"""

from __future__ import annotations

from typing import Callable, Sequence

from custom_components.occp.core.domain.connector_state import ConnectorStateStore
from custom_components.occp.core.domain.events import EventBus
from custom_components.occp.core.domain.meter_values import MeterValueStore
from custom_components.occp.core.domain.models import (
    ChargePointSnapshot,
    ConnectorSnapshot,
    MeterSample,
    StateChangeListener,
    TransactionSnapshot,
)
from custom_components.occp.core.domain.registry import ChargePointRegistryStore
from custom_components.occp.core.domain.transactions import TransactionManager


class QueryServiceImpl:
    def __init__(
        self,
        *,
        registry: ChargePointRegistryStore,
        connectors: ConnectorStateStore,
        transactions: TransactionManager,
        meter_values: MeterValueStore,
        events: EventBus,
    ) -> None:
        self._registry = registry
        self._connectors = connectors
        self._transactions = transactions
        self._meter_values = meter_values
        self._events = events

    def get_charge_points(self) -> Sequence[ChargePointSnapshot]:
        return self._registry.list_all()

    def get_connector(
        self, charge_point_id: str, connector_id: int
    ) -> ConnectorSnapshot | None:
        return self._connectors.get(charge_point_id, connector_id)

    def get_transaction(self, transaction_id: int) -> TransactionSnapshot | None:
        return self._transactions.get(transaction_id)

    def get_active_transactions(
        self, charge_point_id: str | None = None
    ) -> Sequence[TransactionSnapshot]:
        return self._transactions.get_active_transactions(charge_point_id)

    def subscribe(self, listener: StateChangeListener) -> Callable[[], None]:
        return self._events.subscribe(listener)

    def get_connectors(self, charge_point_id: str) -> Sequence[ConnectorSnapshot]:
        """Verbindlicher Bestandteil des ``QueryService``-Protocols seit der
        Ergänzung 2026-08-15 zu ADR-0003 (wie ``get_meter_samples``):
        anders als ``get_connector`` (eine einzelne, bereits bekannte
        ``connector_id``) liefert diese Methode die Liste aller Connectors
        eines Charge Points, benötigt für die Statusübersicht (REQ-0032 AC1)
        und die HA-Geräteabbildung (REQ-0017 AC2).
        """
        return self._connectors.list_for_charge_point(charge_point_id)

    def get_meter_samples(
        self,
        *,
        charge_point_id: str,
        connector_id: int | None = None,
        transaction_id: int | None = None,
    ) -> Sequence[MeterSample]:
        """Verbindlicher Bestandteil des ``QueryService``-Protocols seit der
        Ergänzung 2026-08-15 zu ADR-0003, siehe ``domain.models.MeterSample``.
        """
        if transaction_id is not None:
            return self._meter_values.get_for_transaction(transaction_id)
        if connector_id is not None:
            return self._meter_values.get_for_connector(charge_point_id, connector_id)
        return []
