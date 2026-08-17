"""Connector-Statusverwaltung (REQ-0004): aktueller Status je Connector,
inkl. ``connectorId`` 0 (Ladestation als Ganzes), inkl. ``errorCode``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Sequence

from custom_components.occp.core.domain.models import ConnectorSnapshot


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


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
        self._records: dict[tuple[str, int], _ConnectorRecord] = {}

    def update(
        self,
        charge_point_id: str,
        connector_id: int,
        *,
        status: str,
        error_code: str | None,
    ) -> None:
        self._records[(charge_point_id, connector_id)] = _ConnectorRecord(
            status=status, error_code=error_code
        )

    def get(
        self, charge_point_id: str, connector_id: int
    ) -> ConnectorSnapshot | None:
        record = self._records.get((charge_point_id, connector_id))
        if record is None:
            return None
        return ConnectorSnapshot(
            charge_point_id=charge_point_id,
            connector_id=connector_id,
            status=record.status,
            error_code=record.error_code,
        )

    def list_for_charge_point(
        self, charge_point_id: str
    ) -> Sequence[ConnectorSnapshot]:
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
