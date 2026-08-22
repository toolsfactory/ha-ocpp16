"""Discovery-Shim: Home Assistant lädt dieses Modul auf Integrationsebene, die eigentliche Implementierung lebt in ``config_flow_handler/``."""

from .config_flow_handler import Ocpp16ConfigFlow

__all__ = ["Ocpp16ConfigFlow"]
