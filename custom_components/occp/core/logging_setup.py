"""Logging-Aufbau (REQ-0031).

Ein Logger je Modul (Standard ``logging.getLogger(__name__)``-Muster), plus
ein ``LoggerAdapter`` je aktiver Charge-Point-Verbindung für den
``charge_point_id``-Kontext (AC1/AC2). Log-Level ist zentral konfigurierbar
(AC5); idTags werden vollständig geloggt (Entscheidung REQ-0031, keine
Maskierung); Rotation/Aufbewahrung bleibt bewusst Betreiber-Sache (Non-Goal
REQ-0031).
"""

import logging
import sys


class _DefaultChargePointIdFilter(logging.Filter):
    """Setzt ``charge_point_id`` auf einen Platzhalter für Log-Zeilen ohne Charge-Point-Bezug.

    Damit der Formatter nicht mit ``KeyError`` scheitert (technische
    Einschätzung architect-Agent, siehe REQ-0031).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "charge_point_id"):
            record.charge_point_id = "-"
        return True


LOG_FORMAT = "%(asctime)s %(levelname)-8s [%(charge_point_id)s] %(name)s: %(message)s"


def configure_logging(level: int | str = logging.INFO) -> None:
    """Configure the root logger with OCCP's stdout format and filter."""
    root = logging.getLogger()
    root.setLevel(level)

    for handler in list(root.handlers):
        root.removeHandler(handler)

    stream_handler = logging.StreamHandler(stream=sys.stdout)
    stream_handler.setFormatter(logging.Formatter(LOG_FORMAT))
    stream_handler.addFilter(_DefaultChargePointIdFilter())
    root.addHandler(stream_handler)

    # Die websockets-Bibliothek protokolliert bei DEBUG jedes einzelne Frame
    # (inkl. Handshake-Header) redundant zu unserem eigenen RX/TX-Logging
    # (REQ-0031 AC3, siehe occp.ocpp16.handlers.ChargePointHandler). Das ist
    # kein Bestandteil unserer fachlichen Log-Ausgabe, sondern Bibliotheks-
    # internes Rauschen — daher unabhängig vom konfigurierten Log-Level auf
    # WARNING gedeckelt.
    logging.getLogger("websockets").setLevel(logging.WARNING)


def get_charge_point_logger(charge_point_id: str, *, logger_name: str = "occp.handlers") -> logging.LoggerAdapter:
    """Return a logger adapter that tags every record with `charge_point_id`."""
    base_logger = logging.getLogger(logger_name)
    return logging.LoggerAdapter(base_logger, {"charge_point_id": charge_point_id})
