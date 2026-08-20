"""Connector-Statusverwaltung (REQ-0004).

Aktueller Status je Connector, inkl. ``connectorId`` 0 (Ladestation als
Ganzes), inkl. ``errorCode``.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime

from custom_components.ocpp.core.domain.models import ConnectorSnapshot


def _utcnow() -> datetime:
    return datetime.now(UTC)


@dataclass
class _ConnectorRecord:
    status: str
    error_code: str | None
    updated_at: datetime = field(default_factory=_utcnow)


class ConnectorStateStore:
    """In-memory Status je (charge_point_id, connector_id).

    Schreibzugriff ist ausschließlich den OCPP-1.6-Handlern vorbehalten
    (siehe architecture.md); Lesezugriff erfolgt über ``get``/
    ``list_for_charge_point`` bzw. gebündelt über ``QueryService``.
    """

    def __init__(self) -> None:
        """Initialize with no recorded connectors."""
        self._records: dict[tuple[str, int], _ConnectorRecord] = {}

    def update(
        self,
        charge_point_id: str,
        connector_id: int,
        *,
        status: str,
        error_code: str | None,
    ) -> None:
        """Overwrite the connector's status and error code."""
        self._records[(charge_point_id, connector_id)] = _ConnectorRecord(status=status, error_code=error_code)

    def get(self, charge_point_id: str, connector_id: int) -> ConnectorSnapshot | None:
        """Return the connector's snapshot, or None if unknown."""
        record = self._records.get((charge_point_id, connector_id))
        if record is None:
            return None
        return ConnectorSnapshot(
            charge_point_id=charge_point_id,
            connector_id=connector_id,
            status=record.status,
            error_code=record.error_code,
        )

    def list_for_charge_point(self, charge_point_id: str) -> Sequence[ConnectorSnapshot]:
        """Return every connector's snapshot for the charge point."""
        result = []
        for (cp_id, connector_id), record in self._records.items():
            if cp_id != charge_point_id:
                continue
            result.append(
                ConnectorSnapshot(
                    charge_point_id=cp_id,
                    connector_id=connector_id,
                    status=record.status,
                    error_code=record.error_code,
                )
            )
        return result
