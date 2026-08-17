"""Startkonfiguration des Standalone-Kerns.

Bewusst minimal (keine kuratierte Konfigurationsschlüssel-Liste, siehe
REQ-0014-Entscheidung "rein generisch"): Host/Port für den WebSocket-Server,
Log-Level, Heartbeat-Parameter (REQ-0003) und Pfad zur statischen
Autorisierungsliste (REQ-0005) sind das, was für den Betrieb des Kerns
zwingend nötig ist.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AppConfig:
    host: str = "0.0.0.0"
    port: int = 9000
    log_level: int = logging.INFO
    heartbeat_interval_seconds: int = 300
    heartbeat_grace_period_seconds: float = 5.0
    authorization_file: Path | None = None

    @property
    def heartbeat_timeout_seconds(self) -> float:
        # Entscheidung REQ-0003: 2x vereinbartes Intervall + feste Grace-Period.
        return 2 * self.heartbeat_interval_seconds + self.heartbeat_grace_period_seconds


def _parse_log_level(value: str) -> int:
    level = logging.getLevelName(value.upper())
    if not isinstance(level, int):
        raise argparse.ArgumentTypeError(f"Unbekannter Log-Level: {value}")
    return level


def parse_args(argv: list[str] | None = None) -> AppConfig:
    parser = argparse.ArgumentParser(
        prog="occp",
        description="OCCP Standalone-Kern: OCPP-1.6-Central-System.",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind-Adresse des WebSocket-Servers")
    parser.add_argument("--port", type=int, default=9000, help="Bind-Port des WebSocket-Servers")
    parser.add_argument(
        "--log-level",
        type=_parse_log_level,
        default=logging.INFO,
        help="DEBUG, INFO, WARNING, ERROR (Default: INFO)",
    )
    parser.add_argument(
        "--heartbeat-interval",
        type=int,
        default=300,
        dest="heartbeat_interval_seconds",
        help="An Charge Points kommuniziertes Heartbeat-Intervall in Sekunden",
    )
    parser.add_argument(
        "--heartbeat-grace-period",
        type=float,
        default=5.0,
        dest="heartbeat_grace_period_seconds",
        help="Zusätzliche Toleranz in Sekunden über 2x Heartbeat-Intervall hinaus",
    )
    parser.add_argument(
        "--authorization-file",
        type=Path,
        default=None,
        help="JSON-Datei mit statischer idTag-Autorisierungsliste (REQ-0005)",
    )
    args = parser.parse_args(argv)
    return AppConfig(
        host=args.host,
        port=args.port,
        log_level=args.log_level,
        heartbeat_interval_seconds=args.heartbeat_interval_seconds,
        heartbeat_grace_period_seconds=args.heartbeat_grace_period_seconds,
        authorization_file=args.authorization_file,
    )
