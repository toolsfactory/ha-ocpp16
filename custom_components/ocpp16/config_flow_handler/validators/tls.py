"""Validiert ein TLS-Zertifikat/Schlüssel-Paar für direktes ``wss://`` (Phase 5) vor der Übernahme in den Flow."""

from pathlib import Path
import ssl

from custom_components.ocpp16.core.transport import build_ssl_context


def validate_tls_certificate(certificate_path: str, private_key_path: str) -> ssl.SSLContext:
    """Validate that `certificate_path`/`private_key_path` form a loadable TLS server certificate pair.

    Läuft synchron -- Aufrufer müssen ``hass.async_add_executor_job`` nutzen.
    Wirft ``OSError`` (nicht lesbar/vorhanden) oder ``ssl.SSLError`` (kein gültiges
    PEM-Zertifikat/Schlüssel-Paar bzw. Mismatch) bei ungültigem Inhalt. Ruft absichtlich
    den echten Loader (``build_ssl_context``) auf, statt die Prüfung separat
    nachzubilden -- die Flow-Validierung kann so nie von dem abweichen, was
    ``async_setup_entry()`` tatsächlich beim Start des WebSocket-Servers macht.
    """
    return build_ssl_context(Path(certificate_path), Path(private_key_path))
