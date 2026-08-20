"""Bekannter Nachbau-Nachteil von python-ocpp (siehe ADR-0001).

Konsequenzen/Negativ: "Deckt die Bibliothek eine benötigte OCPP-1.6-Nuance
nicht oder fehlerhaft ab, entsteht ... ein lokaler Workaround".

``ocpp.messages._validate_payload`` meldet Schema-Verletzungen (z. B.
zusätzliche/unbekannte Felder) unabhängig von der OCPP-Version immer als
``FormatViolationError`` (``errorCode`` "FormatViolation", OCPP-2.0.1-
Schreibweise). Für strikte OCPP-1.6-Konformität verlangt die Spezifikation
(inkl. der bekannten Errata, siehe ``ocpp.exceptions.FormationViolationError``
-Docstring in der Bibliothek selbst) die Schreibweise "FormationViolation" —
REQ-0015 AC2 fordert genau diesen Wortlaut. Verifiziert gegen python-ocpp
2.1.0 (aktuell zum Zeitpunkt der Implementierung): ``_validate_payload``
verzweigt nicht nach ``ocpp_version``, sondern raised in allen Fällen
``FormatViolationError``.

Da die Bibliothek Schema-Validierungsfehler intern (in
``ChargePoint._handle_call``) auffängt und direkt als ``CallError`` auf die
Verbindung schreibt, bevor unser eigener Handler-Code eingreifen könnte, ist
ein Patch der Exception-Klasse selbst der einzige Weg, das ohne Nachbau der
Bibliotheksinterna zu korrigieren.

Zweiter, analoger Fall (REQ-0015 AC1a/AC1b): ``ocpp.charge_point.
_raise_key_error`` (aufgerufen für eine unbekannte bzw. nicht behandelte
Action, siehe ``ChargePoint.route_message``) vertauscht die ``errorCode``-
Werte von ``NotImplementedError`` und ``NotSupportedError`` exakt umgekehrt
zur OCPP-1.6-Spezifikation: Standardmäßig liefert ``NotImplementedError.code
== "NotImplemented"`` mit der Bedeutung "Requested Action is recognized but
not supported" (spezifikationsgemäß eigentlich "NotSupported") und
``NotSupportedError.code == "NotSupported"`` mit der Bedeutung "Requested
Action is not known by receiver" (spezifikationsgemäß eigentlich
"NotImplemented"). Die jeweiligen ``default_description``-Texte sind bereits
korrekt der jeweils anderen Bedeutung zugeordnet und bleiben unverändert —
nur ``code`` wird getauscht.

Dritter Fall (ADR-0005, REQ-0006 AC4/REQ-0007 AC5): ``ocpp.messages.
get_validator`` lädt für jede Action/``message_type_id`` das passende
JSON-Schema von der Platte und liefert einen gecachten
``jsonschema.Draft4Validator`` zurück, gegen den ``_validate_payload``
(aufgerufen aus ``ChargePoint._handle_call``, **vor** jedem eigenen
``@on``-Handler) jede eingehende Nachricht prüft. Laut Schema sind
``meterStart`` (``StartTransaction``) und ``meterStop`` (``StopTransaction``)
strikt vom Typ ``"integer"`` — reale Charge-Point-Implementierungen senden
dort beobachtet auch Fließkommazahlen (z. B. `41.666666666666664`), was ohne
diesen Workaround eine `TypeConstraintViolationError` auslöst, bevor
`on_start_transaction`/`on_stop_transaction` (`src/ocpp/ocpp16/handlers.py`)
überhaupt erreicht wird. Per Produktentscheidung (ADR-0005) soll OCPP solche
Werte stattdessen tolerieren und runden. Da die Bibliothek das geladene
Schema pro Action cached, patchen wir ``get_validator`` selbst: nach dem
Original-Aufruf wird für die Actions ``StartTransaction``/``StopTransaction``
der ``type`` des jeweiligen Feldes (falls im Schema vorhanden) von
``"integer"`` auf ``["integer", "number"]`` erweitert. Die eigentliche
Rundung auf `int` erfolgt weiterhin im Handler (ADR-0005), nicht hier — dieser
Patch sorgt nur dafür, dass die Nachricht die Schema-Validierung überhaupt
passiert.
"""

from collections.abc import Callable

from ocpp.exceptions import FormatViolationError, NotImplementedError, NotSupportedError
import ocpp.messages

FormatViolationError.code = "FormationViolation"
NotImplementedError.code = "NotSupported"
NotSupportedError.code = "NotImplemented"

# Der wahre Original-``get_validator`` wird am ``ocpp.messages``-Modul selbst
# gemerkt (nicht nur hier lokal), damit ein wiederholter Import/Reload dieses
# Moduls (siehe test_req_0015_ac2_patch_is_idempotent_across_repeated_imports)
# nicht versehentlich den bereits gepatchten Wrapper als "Original" übernimmt
# -- das würde zu unbegrenzter Selbst-Rekursion führen.
if not hasattr(ocpp.messages, "_ocpp_original_get_validator"):
    ocpp.messages._ocpp_original_get_validator = ocpp.messages.get_validator  # noqa: SLF001 # type: ignore[attr-defined]

_original_get_validator = ocpp.messages._ocpp_original_get_validator  # noqa: SLF001 # type: ignore[attr-defined]

_TOLERANT_NUMERIC_FIELDS = {
    "StartTransaction": "meterStart",
    "StopTransaction": "meterStop",
}


def _tolerant_get_validator(message_type_id: int, action: str, ocpp_version: str, parse_float: Callable = float):
    validator = _original_get_validator(message_type_id, action, ocpp_version, parse_float)
    field_name = _TOLERANT_NUMERIC_FIELDS.get(action)
    if field_name is not None:
        # jsonschema types Validator.schema as `dict | bool` (a JSON Schema value can
        # itself be a bare bool) -- for python-ocpp's message schemas it is always a dict.
        schema: dict = validator.schema  # type: ignore[assignment]
        field_schema = schema.get("properties", {}).get(field_name)
        if field_schema is not None and field_schema.get("type") == "integer":
            field_schema["type"] = ["integer", "number"]
    return validator


ocpp.messages.get_validator = _tolerant_get_validator
