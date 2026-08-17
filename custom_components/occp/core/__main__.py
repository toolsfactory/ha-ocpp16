"""Startpunkt des Standalone-Kerns: ``python -m occp`` bzw. das ``occp``-Konsolenskript.

Fährt WebSocket-Server, Logging und (bei vorhandenem Terminal) die
interaktive Konsole zusammen hoch.
"""

import asyncio
import logging

from custom_components.occp.core.app import CentralSystemApp
from custom_components.occp.core.config import parse_args
from custom_components.occp.core.logging_setup import configure_logging

logger = logging.getLogger(__name__)


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments and run the standalone core until interrupted."""
    config = parse_args(argv)
    configure_logging(config.log_level)

    app = CentralSystemApp(config)
    try:
        asyncio.run(app.run())
    except KeyboardInterrupt:
        logger.info("Beendet durch Benutzer (KeyboardInterrupt).")


if __name__ == "__main__":
    main()
