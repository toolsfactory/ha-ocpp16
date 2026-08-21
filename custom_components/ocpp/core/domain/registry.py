"""Charge-Point-Registry (REQ-0002): Verbindungs-/Boot-Status je Charge Point.

Schreibender Zugriff (``register_connection``, ``mark_boot``,
``mark_disconnected``) ist ausschließlich für die OCPP-1.6-Handler und den
Transport gedacht (siehe architecture.md); der lesende Teil implementiert
strukturell das in ``docs/architecture/interfaces.md`` (ADR-0003)
verbindliche ``ChargePointRegistry``-Protocol.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from custom_components.ocpp.core.domain.connection import ChargePointConnection
from custom_components.ocpp.core.domain.models import ChargePointSnapshot, ConnectionStatus


@dataclass
class _ChargePointRecord:
    charge_point_id: str
    connection_status: ConnectionStatus
    last_boot_at: datetime | None = None
    last_heartbeat_at: datetime | None = None
    vendor: str | None = None
    model: str | None = None
    firmware_version: str | None = None
    reconnect_count: int = 0

    def to_snapshot(self) -> ChargePointSnapshot:
        return ChargePointSnapshot(
            charge_point_id=self.charge_point_id,
            connection_status=self.connection_status,
            last_boot_at=self.last_boot_at,
            last_heartbeat_at=self.last_heartbeat_at,
            vendor=self.vendor,
            model=self.model,
            firmware_version=self.firmware_version,
            reconnect_count=self.reconnect_count,
        )


class ChargePointRegistryStore:
    """Verbindungs-/Boot-Status je Charge Point (REQ-0002)."""

    def __init__(self) -> None:
        """Initialize with no recorded charge points."""
        self._records: dict[str, _ChargePointRecord] = {}
        self._handlers: dict[str, ChargePointConnection] = {}

    # -- schreibender Zugriff (intern, Transport/Handler) -------------------

    def register_connection(self, charge_point_id: str, handler: ChargePointConnection) -> ChargePointConnection | None:
        """Registriert eine neue aktive Verbindung.

        Gibt die zuvor aktive Verbindung unter derselben Identität zurück
        (REQ-0001 AC4: Aufrufer muss diese aktiv schließen, "neue Verbindung
        übernimmt") oder ``None``, falls es keine gab.
        """
        previous = self._handlers.get(charge_point_id)
        self._handlers[charge_point_id] = handler
        record = self._records.get(charge_point_id)
        if record is None:
            record = _ChargePointRecord(
                charge_point_id=charge_point_id,
                connection_status=ConnectionStatus.ONLINE,
            )
            self._records[charge_point_id] = record
        else:
            # Nicht die erste Verbindung dieses Charge Points -- zaehlt als Reconnect,
            # unabhaengig davon, ob es ein sauberer Reconnect oder eine Uebernahme
            # (REQ-0001 AC4, `previous is not None`) ist.
            record.connection_status = ConnectionStatus.ONLINE
            record.reconnect_count += 1
        return previous

    def mark_boot(
        self,
        charge_point_id: str,
        *,
        vendor: str | None,
        model: str | None,
        firmware_version: str | None,
        boot_at: datetime,
    ) -> None:
        """Record a BootNotification, creating the charge point record if new."""
        record = self._records.setdefault(
            charge_point_id,
            _ChargePointRecord(
                charge_point_id=charge_point_id,
                connection_status=ConnectionStatus.ONLINE,
            ),
        )
        record.vendor = vendor
        record.model = model
        record.firmware_version = firmware_version
        record.last_boot_at = boot_at

    def mark_heartbeat(self, charge_point_id: str, at: datetime) -> None:
        """Record a Heartbeat. No-op if the charge point isn't registered yet.

        A connection is always registered (``register_connection``) before any OCPP message,
        including the first ``Heartbeat``, can arrive -- this mirrors ``mark_disconnected``'s
        existing defensive style rather than assuming that invariant can never be violated.
        """
        record = self._records.get(charge_point_id)
        if record is not None:
            record.last_heartbeat_at = at

    def mark_disconnected(self, charge_point_id: str, handler: ChargePointConnection) -> None:
        """Markiert offline, aber nur wenn ``handler`` noch aktuell ist.

        Verhindert, dass das Aufräumen einer aktiv geschlossenen alten
        Verbindung (REQ-0001 AC4) fälschlich die inzwischen übernehmende neue
        Verbindung als offline markiert.
        """
        if self._handlers.get(charge_point_id) is not handler:
            return
        del self._handlers[charge_point_id]
        record = self._records.get(charge_point_id)
        if record is not None:
            record.connection_status = ConnectionStatus.OFFLINE

    def get_active_connection(self, charge_point_id: str) -> ChargePointConnection | None:
        """Return the currently registered connection handler, if any."""
        return self._handlers.get(charge_point_id)

    # -- lesender Zugriff (ChargePointRegistry-Protocol) ---------------------

    def get(self, charge_point_id: str) -> ChargePointSnapshot | None:
        """Return the charge point's snapshot, or None if unknown."""
        record = self._records.get(charge_point_id)
        return record.to_snapshot() if record is not None else None

    def list_all(self) -> Sequence[ChargePointSnapshot]:
        """Return snapshots for every known charge point."""
        return [record.to_snapshot() for record in self._records.values()]
