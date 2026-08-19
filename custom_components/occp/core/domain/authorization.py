"""Autorisierungsquelle (REQ-0005).

Statische Konfiguration hinter einer austauschbaren
``AuthorizationProvider``-Schnittstelle (Entscheidung siehe REQ-0005), damit
spätere Quellen (z. B. eine HA-Helper-Entity in Stufe 4) ohne Bruch an der
Handler-Logik nachgezogen werden können.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
import json
from pathlib import Path
from typing import Protocol


class IdTagStatus(StrEnum):
    """OCPP-1.6-``idTagInfo.status``-Werte (Authorize.conf/StartTransaction.conf)."""

    ACCEPTED = "Accepted"
    BLOCKED = "Blocked"
    EXPIRED = "Expired"
    INVALID = "Invalid"


@dataclass(frozen=True)
class AuthorizationDecision:
    """Ergebnis einer `AuthorizationProvider.authorize`-Anfrage."""

    status: IdTagStatus
    parent_id_tag: str | None = None
    expiry_date: datetime | None = None


class AuthorizationProvider(Protocol):
    """Austauschbare Autorisierungsquelle für idTags."""

    def authorize(self, id_tag: str) -> AuthorizationDecision:
        """Return the authorization decision for `id_tag`."""
        ...


@dataclass(frozen=True)
class StaticIdTagEntry:
    """Ein einzelner Eintrag der statischen Autorisierungsliste."""

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
        """Initialize the provider from `entries`, keyed by idTag."""
        self._entries: dict[str, StaticIdTagEntry] = {entry.id_tag: entry for entry in entries}

    @classmethod
    def empty(cls) -> StaticAuthorizationProvider:
        """Return a provider with no configured idTags."""
        return cls(())

    @classmethod
    def from_json_file(cls, path: Path) -> StaticAuthorizationProvider:
        """Lädt die Liste aus einer JSON-Datei.

        Erwartetes Format::

            {
              "idTags": {
                "ABC123": {"blocked": false, "parentIdTag": null, "expiryDate": null},
                "DEF456": {"blocked": true}
              }
            }

        Validiert die Struktur explizit statt sich auf ``AttributeError``/``TypeError`` aus
        fehlgeschlagenen ``.get()``/``.items()``-Aufrufen zu verlassen -- Aufrufer (Config-/
        Options-Flow) fangen gezielt ``ValueError`` ab, nicht beliebige Exceptions.
        """
        raw = json.loads(path.read_text(encoding="utf-8"))
        # ValueError, nicht TypeError (TRY004), ist hier bewusst: die Aufrufer in
        # config_flow.py/options_flow.py fangen ausschließlich (OSError, ValueError) ab, um
        # zwischen "unlesbar/ungültiger Inhalt" (Formularfehler) und einem echten Programmierfehler
        # zu unterscheiden -- ein TypeError würde dort unbehandelt durchschlagen.
        if not isinstance(raw, dict):
            raise ValueError(f"Autorisierungsdatei: Wurzelelement muss ein Objekt sein, ist {type(raw).__name__}.")  # noqa: TRY004
        id_tags = raw.get("idTags", {})
        if not isinstance(id_tags, dict):
            raise ValueError(f"Autorisierungsdatei: 'idTags' muss ein Objekt sein, ist {type(id_tags).__name__}.")  # noqa: TRY004

        entries = []
        for id_tag, fields in id_tags.items():
            if not isinstance(fields, dict):
                raise ValueError(f"Autorisierungsdatei: Eintrag für idTag '{id_tag}' muss ein Objekt sein.")  # noqa: TRY004
            blocked = fields.get("blocked", False)
            if not isinstance(blocked, bool):
                raise ValueError(f"Autorisierungsdatei: 'blocked' für idTag '{id_tag}' muss ein Boolean sein.")  # noqa: TRY004
            expiry_raw = fields.get("expiryDate")
            if expiry_raw is not None and not isinstance(expiry_raw, str):
                raise ValueError(f"Autorisierungsdatei: 'expiryDate' für idTag '{id_tag}' muss eine Zeichenkette sein.")
            entries.append(
                StaticIdTagEntry(
                    id_tag=id_tag,
                    blocked=blocked,
                    parent_id_tag=fields.get("parentIdTag"),
                    expiry_date=(datetime.fromisoformat(expiry_raw) if expiry_raw else None),
                )
            )
        return cls(entries)

    def authorize(self, id_tag: str) -> AuthorizationDecision:
        """Return the decision for `id_tag` based on the static list."""
        entry = self._entries.get(id_tag)
        if entry is None:
            return AuthorizationDecision(status=IdTagStatus.INVALID)
        if entry.blocked:
            return AuthorizationDecision(status=IdTagStatus.BLOCKED, parent_id_tag=entry.parent_id_tag)
        if entry.expiry_date is not None and entry.expiry_date < datetime.now(UTC):
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
