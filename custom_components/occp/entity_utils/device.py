"""Geräte-/Entity-Modell-Helfer (REQ-0017, ADR-0008 Abschnitt 3).

Charge Point = HA-Device, Connector = eigenes Sub-Device via ``via_device``.
``connectorId 0`` bekommt laut ADR-0008 **kein** eigenes Sub-Device --
etwaige charge-point-weite Entities hängen direkt am Charge-Point-Device
(siehe ``connector_device_info`` unten).
"""

from custom_components.occp.const import DOMAIN
from custom_components.occp.core.domain.models import ChargePointSnapshot
from homeassistant.helpers.device_registry import DeviceInfo


def charge_point_device_info(charge_point_id: str, snapshot: ChargePointSnapshot | None) -> DeviceInfo:
    """Device-Info für den Charge Point selbst (REQ-0017 AC1)."""
    return DeviceInfo(
        identifiers={(DOMAIN, charge_point_id)},
        name=f"Ladestation {charge_point_id}",
        manufacturer=snapshot.vendor if snapshot else None,
        model=snapshot.model if snapshot else None,
        sw_version=snapshot.firmware_version if snapshot else None,
    )


def connector_identifier(charge_point_id: str, connector_id: int) -> str:
    """``unique_id``-/Device-Identifier-Bestandteil eines Connectors."""
    return f"{charge_point_id}_{connector_id}"


def parse_connector_identifier(identifier: str) -> tuple[str, int] | None:
    """Kehrfunktion zu ``connector_identifier``.

    ``charge_point_id`` kann selbst Unterstriche enthalten, deshalb Split
    ausschließlich am **letzten** Unterstrich. Gibt ``None`` zurück, wenn der
    Identifier nicht dem erwarteten ``<cpId>_<connectorId>``-Schema
    entspricht (z. B. weil er auf das Charge-Point-Device selbst zeigt).
    """
    if "_" not in identifier:
        return None
    charge_point_id, _, connector_part = identifier.rpartition("_")
    if not connector_part.isdigit():
        return None
    return charge_point_id, int(connector_part)


def connector_device_info(charge_point_id: str, connector_id: int) -> DeviceInfo:
    """Device-Info für einen Connector (REQ-0017 AC2).

    ``connectorId 0`` (ganze Ladestation, OCPP 1.6) bekommt laut ADR-0008
    kein eigenes Sub-Device -- Aufrufer für connectorId 0 sollten stattdessen
    ``charge_point_device_info`` direkt verwenden.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, connector_identifier(charge_point_id, connector_id))},
        name=f"Ladepunkt {connector_id}",
        via_device=(DOMAIN, charge_point_id),
    )
