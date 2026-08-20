"""OCPP-1.6-Handler-Schicht: kapselt python-ocpp (ADR-0001) hinter den Kern-Domänenklassen.

Diese Schicht importiert ausschließlich ``ocpp.v16`` (nie ``ocpp.v201``,
siehe REQ-0027/ADR-0001) und ist der einzige Ort im Kern, an dem
``ocpp.*``-Typen sichtbar sind.
"""

from custom_components.ocpp.core.ocpp16 import _compat  # noqa: F401 - Patch beim Import aktivieren
