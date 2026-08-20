"""Validiert den Pfad zur idTag-Autorisierungsliste vor der Übernahme in den Flow."""

from pathlib import Path

from custom_components.ocpp.core.domain.authorization import StaticAuthorizationProvider


def validate_authorization_file(path_str: str) -> StaticAuthorizationProvider:
    """Validate that `path_str` points at a readable, structurally valid authorization file.

    Läuft synchron -- Aufrufer müssen ``hass.async_add_executor_job`` nutzen.
    Wirft ``OSError`` (nicht lesbar/vorhanden) oder ``ValueError`` (ungültiges JSON oder
    eine Struktur, die ``from_json_file`` nicht akzeptiert) bei ungültigem Inhalt. Ruft
    absichtlich den echten Loader (``StaticAuthorizationProvider.from_json_file``) auf,
    statt die Struktur separat nachzubilden -- die Flow-Validierung kann so nie von dem
    abweichen, was ``async_setup_entry()`` tatsächlich mit der Datei macht. Gibt den
    geladenen Provider zurück, damit Aufrufer ihn (z. B. für einen Default-idTag-Check)
    weiterverwenden können, ohne die Datei ein zweites Mal zu laden.
    """
    return StaticAuthorizationProvider.from_json_file(Path(path_str))
