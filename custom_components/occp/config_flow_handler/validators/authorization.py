"""Validiert den Pfad zur idTag-Autorisierungsliste vor der Übernahme in den Flow."""

from pathlib import Path

from custom_components.occp.core.domain.authorization import StaticAuthorizationProvider


def validate_authorization_file(path_str: str) -> None:
    """Validate that `path_str` points at a readable, JSON-parsable authorization file.

    Läuft synchron -- Aufrufer müssen ``hass.async_add_executor_job`` nutzen.
    Wirft ``OSError`` (nicht lesbar/vorhanden) oder ``ValueError``
    (``json.JSONDecodeError`` ist eine Unterklasse davon) bei ungültigem
    Inhalt. Ruft absichtlich den echten Loader
    (``StaticAuthorizationProvider.from_json_file``) auf, statt die
    Struktur separat nachzubilden -- die Flow-Validierung kann so nie von
    dem abweichen, was ``async_setup_entry()`` tatsächlich mit der Datei
    macht.
    """
    StaticAuthorizationProvider.from_json_file(Path(path_str))
