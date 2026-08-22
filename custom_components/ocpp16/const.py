"""Konstanten des HA-Layers (custom_components/ocpp16/).

Bewusst getrennt vom Standalone-Kern (``core/``) gehalten -- keine
``homeassistant.*``-Importe im Kern (CLAUDE.md).
"""

DOMAIN = "ocpp16"

PLATFORMS = ["button", "number", "sensor", "switch"]

# -- Config-Flow-Felder (REQ-0016, ADR-0008 Abschnitt 4) --------------------
CONF_HOST = "host"
CONF_PORT = "port"
CONF_AUTHORIZATION_FILE = "authorization_file"
# Additiv zum ADR-0008-Feldsatz: fest konfiguriertes idTag für
# RemoteStartTransaction (REQ-0020, Entscheidung "ein fest konfiguriertes
# idTag pro Charge Point"). Da eine Central-System-Instanz (= ein Config
# Entry) bereits heute genau eine gemeinsame Autorisierungsliste
# (``authorization_file``) fuer alle daran angeschlossenen Charge Points
# verwendet (kein Per-Charge-Point-Scope im Kern, siehe AppConfig), ist ein
# einzelnes, Config-Entry-weites idTag hierzu konsistent -- siehe
# Abschlussbericht des developer-Agenten fuer die vollstaendige Begruendung.
CONF_DEFAULT_ID_TAG = "default_id_tag"
# Additiv: Obergrenze für das number.power_limit_w-Entity (kein Vertragsbestandteil,
# siehe INTEROP_CONTRACT.md) -- nicht fest codiert, weil das real angeschlossene
# Ladegerät selbst konfigurierbar ist (z. B. 11 kW oder 22 kW je nach Anschluss).
CONF_MAX_POWER_LIMIT_W = "max_power_limit_w"
# Additiv: optionales TLS-Zertifikat/Schlüssel-Paar für direktes wss:// ohne Reverse
# Proxy (siehe DECISIONS.md "Direct built-in TLS instead of a reverse proxy for
# wss://"). Verbindungskritisch wie Host/Port, daher in entry.data statt
# entry.options -- additiv und per entry.data.get(...) gelesen, keine Migration nötig
# (Präzedenzfall max_power_limit_w).
CONF_CERTIFICATE_PATH = "certificate_path"
CONF_PRIVATE_KEY_PATH = "private_key_path"

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9000
DEFAULT_MAX_POWER_LIMIT_W = 22000.0

# -- Fähigkeit-7-Discovery-Bitmask (ADR-0010) --------------------------------
CAP_BIT_CURRENT_POWER = 1  # Fähigkeit 1
CAP_BIT_STATE = 2  # Fähigkeit 2
CAP_BIT_SET_LIMIT = 4  # Fähigkeit 3
CAP_BIT_CLEAR_LIMIT = 8  # Fähigkeit 4
CAP_BIT_READ_LIMIT = 16  # Fähigkeit 5
CAP_BIT_AVAILABILITY = 32  # Fähigkeit 6
CAP_BIT_AUTHORIZE = 64  # Fähigkeit 8
CAP_BIT_START_RELEASE = 128  # Fähigkeit 9 (OCPP: immer 0, siehe ADR-0010)

# OCPP bietet Fähigkeit 1-6 und 8 immer an (ADR-0010, Tabelle) -- Fähigkeit 9
# nicht (REQ-0020 Non-Goals).
SUPPORTED_CAPABILITIES = (
    CAP_BIT_CURRENT_POWER
    | CAP_BIT_STATE
    | CAP_BIT_SET_LIMIT
    | CAP_BIT_CLEAR_LIMIT
    | CAP_BIT_READ_LIMIT
    | CAP_BIT_AVAILABILITY
    | CAP_BIT_AUTHORIZE
)
SUPPORTED_PHASES = [1, 2, 3]

# -- REQ-0019: fünfwertiges Status-Modell ------------------------------------
STATE_NOT_CONNECTED = "not_connected"
STATE_READY = "ready"
STATE_CHARGING = "charging"
STATE_UNAVAILABLE = "unavailable"
STATE_ERROR = "error"

RAW_STATUS_TO_STATE: dict[str, str] = {
    "Available": STATE_NOT_CONNECTED,
    "Preparing": STATE_READY,
    "Charging": STATE_CHARGING,
    "SuspendedEVSE": STATE_READY,
    "SuspendedEV": STATE_READY,
    "Finishing": STATE_READY,
    "Reserved": STATE_UNAVAILABLE,
    "Unavailable": STATE_UNAVAILABLE,
    "Faulted": STATE_ERROR,
}

# -- Fähigkeit 1/5-Measurand (ADR-0010) --------------------------------------
MEASURAND_POWER_ACTIVE_IMPORT = "Power.Active.Import"

# -- Active-Phases-Sensor (kein Interop-Vertrag-Bestandteil) ----------------
MEASURAND_CURRENT_IMPORT = "Current.Import"

# -- Session-Energy-Sensor (kein Interop-Vertrag-Bestandteil) ---------------
MEASURAND_ENERGY_ACTIVE_IMPORT_REGISTER = "Energy.Active.Import.Register"
