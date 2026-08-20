"""Konstanten des HA-Layers (custom_components/ocpp/).

Bewusst getrennt vom Standalone-Kern (``src/ocpp/``) gehalten -- keine
``homeassistant.*``-Importe im Kern (CLAUDE.md).
"""

DOMAIN = "ocpp"

PLATFORMS = ["sensor", "switch"]

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

DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 9000

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
