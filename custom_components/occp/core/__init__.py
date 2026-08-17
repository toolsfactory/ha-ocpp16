"""OCCP standalone core: OCPP 1.6 Central System, independent of Home Assistant.

See CLAUDE.md and docs/architecture/architecture.md for the stage plan and
the Standalone-Kern/HA-Layer separation rule this package must not violate
(no ``homeassistant.*`` imports here).
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
