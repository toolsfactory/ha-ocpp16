"""Autorisierungsquelle (REQ-0005): statische Konfiguration hinter einer
austauschbaren ``AuthorizationProvider``-Schnittstelle (Entscheidung siehe
REQ-0005), damit spätere Quellen (z. B. eine HA-Helper-Entity in Stufe 4)
ohne Bruch an der Handler-Logik nachgezogen werden können.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Iterable, Protocol


class IdTagStatus(str, Enum):
    ACCEPTED = "Accepted"
    BLOCKED = "Blocked"
    EXPIRED = "Expired"
    INVALID = "Invalid"


@dataclass(frozen=True)
class AuthorizationDecision:
    status: IdTagStatus
    parent_id_tag: str | None = None
    expiry_date: datetime | None = None


class AuthorizationProvider(Protocol):
    def authorize(self, id_tag: str) -> AuthorizationDecision: ...


@dataclass(frozen=True)
class StaticIdTagEntry:
    id_tag: str
    blocked: bool = False
    parent_id_tag: str | None = None
    expiry_date: datetime | None = None


class StaticAuthorizationProvider:
    """Statische, beim Start geladene Autorisierungsliste (REQ-0005 AC4).

    Kein ``SendLocalList``, keine Verwaltungsoberfläche (Non-Goals REQ-0005)
    — die Liste wird einmalig beim Start aus Konfiguration übernommen.
    """

    def __init__(self, entries: Iterable[StaticIdTagEntry]) -> None:
        self._entries: dict[str, StaticIdTagEntry] = {
            entry.id_tag: entry for entry in entries
        }

    @classmethod
    def empty(cls) -> "StaticAuthorizationProvider":
        return cls(())

    @classmethod
    def from_json_file(cls, path: Path) -> "StaticAuthorizationProvider":
        """Lädt die Liste aus einer JSON-Datei.

        Erwartetes Format::

            {
              "idTags": {
                "ABC123": {"blocked": false, "parentIdTag": null, "expiryDate": null},
                "DEF456": {"blocked": true}
              }
            }
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        entries = []
        for id_tag, fields in raw.get("idTags", {}).items():
            expiry_raw = fields.get("expiryDate")
            entries.append(
                StaticIdTagEntry(
                    id_tag=id_tag,
                    blocked=bool(fields.get("blocked", False)),
                    parent_id_tag=fields.get("parentIdTag"),
                    expiry_date=(
                        datetime.fromisoformat(expiry_raw) if expiry_raw else None
                    ),
                )
            )
        return cls(entries)

    def authorize(self, id_tag: str) -> AuthorizationDecision:
        entry = self._entries.get(id_tag)
        if entry is None:
            return AuthorizationDecision(status=IdTagStatus.INVALID)
        if entry.blocked:
            return AuthorizationDecision(
                status=IdTagStatus.BLOCKED, parent_id_tag=entry.parent_id_tag
            )
        if entry.expiry_date is not None and entry.expiry_date < datetime.now(
            timezone.utc
        ):
            return AuthorizationDecision(
                status=IdTagStatus.EXPIRED,
                parent_id_tag=entry.parent_id_tag,
                expiry_date=entry.expiry_date,
            )
        return AuthorizationDecision(
            status=IdTagStatus.ACCEPTED,
            parent_id_tag=entry.parent_id_tag,
            expiry_date=entry.expiry_date,
        )
