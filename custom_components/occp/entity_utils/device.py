"""Geräte-/Entity-Modell-Helfer (REQ-0017, ADR-0008 Abschnitt 3).

Charge Point = HA-Device, Connector = eigenes Sub-Device via ``via_device``.
``connectorId 0`` bekommt laut ADR-0008 **kein** eigenes Sub-Device --
etwaige charge-point-weite Entities hängen direkt am Charge-Point-Device
(siehe ``connector_device_info`` unten).

Jeder Identifier ist mit der ``entry_id`` der besitzenden Central-System-
Instanz präfixiert: zwei Instanzen, die zufällig dieselbe ``chargePointId``
verbinden (die ID wählt der Charge Point, nicht OCCP), dürfen keine
kollidierenden Device-/Entity-Identifier erzeugen. ``entry_id`` ist eine
ULID und enthält daher nie ``:``, sodass das Abtrennen am ersten ``:``
immer eindeutig ist.
"""

from custom_components.occp.const import DOMAIN
from custom_components.occp.core.domain.models import ChargePointSnapshot
from homeassistant.helpers.device_registry import DeviceInfo


def charge_point_identifier(entry_id: str, charge_point_id: str) -> str:
    """``unique_id``-/Device-Identifier-Bestandteil des Charge Points selbst."""
    return f"{entry_id}:{charge_point_id}"


def connector_identifier(entry_id: str, charge_point_id: str, connector_id: int) -> str:
    """``unique_id``-/Device-Identifier-Bestandteil eines Connectors.

    Längenpräfix für ``charge_point_id`` statt eines schlichten Trennzeichens:
    ein reines ``f"{a}_{b}"`` ist mehrdeutig, sobald ``a`` selbst auf
    ``_<Ziffern>`` enden kann (z. B. ``charge_point_id="station_1"`` mit
    Connector 0 vs. ``charge_point_id="station"`` mit Connector 1) --
    Längenpräfixierung macht die Aufteilung unabhängig vom Inhalt von
    ``charge_point_id`` eindeutig.
    """
    return f"{entry_id}:{len(charge_point_id)}:{charge_point_id}:{connector_id}"


def parse_connector_identifier(identifier: str) -> tuple[str, int] | None:
    """Kehrfunktion zu ``connector_identifier`` -- gibt ``(charge_point_id, connector_id)`` zurück.

    Die ``entry_id`` wird verworfen, statt zurückgegeben: Aufrufer kennen sie
    bereits unabhängig über ``DeviceEntry.config_entry_id`` (die maßgebliche,
    gescopte Quelle) und sollen sich nicht auf den Identifier-Inhalt dafür
    verlassen. Gibt ``None`` zurück, wenn der Identifier nicht dem erwarteten
    Schema entspricht (z. B. weil er auf das Charge-Point-Device selbst
    zeigt).
    """
    _entry_id, sep, rest = identifier.partition(":")
    if not sep:
        return None
    length_part, sep, rest = rest.partition(":")
    if not sep or not length_part.isdigit():
        return None
    length = int(length_part)
    if len(rest) <= length or rest[length] != ":":
        return None
    charge_point_id = rest[:length]
    connector_part = rest[length + 1 :]
    if not connector_part.isdigit():
        return None
    return charge_point_id, int(connector_part)


def parse_charge_point_identifier(identifier: str) -> str | None:
    """Kehrfunktion zu ``charge_point_identifier`` -- gibt ``charge_point_id`` zurück.

    Gibt ``None`` zurück, wenn der Identifier dem Connector-Schema
    entspricht (``parse_connector_identifier``) statt dem
    Charge-Point-Schema.
    """
    if parse_connector_identifier(identifier) is not None:
        return None
    _entry_id, sep, charge_point_id = identifier.partition(":")
    if not sep:
        return None
    return charge_point_id


def charge_point_device_info(entry_id: str, charge_point_id: str, snapshot: ChargePointSnapshot | None) -> DeviceInfo:
    """Device-Info für den Charge Point selbst (REQ-0017 AC1)."""
    return DeviceInfo(
        identifiers={(DOMAIN, charge_point_identifier(entry_id, charge_point_id))},
        name=f"Charge Point {charge_point_id}",
        manufacturer=snapshot.vendor if snapshot else None,
        model=snapshot.model if snapshot else None,
        sw_version=snapshot.firmware_version if snapshot else None,
    )


def connector_device_info(entry_id: str, charge_point_id: str, connector_id: int) -> DeviceInfo:
    """Device-Info für einen Connector (REQ-0017 AC2).

    ``connectorId 0`` (ganze Ladestation, OCPP 1.6) bekommt laut ADR-0008
    kein eigenes Sub-Device -- Aufrufer für connectorId 0 sollten stattdessen
    ``charge_point_device_info`` direkt verwenden.
    """
    return DeviceInfo(
        identifiers={(DOMAIN, connector_identifier(entry_id, charge_point_id, connector_id))},
        name=f"Connector {connector_id}",
        via_device=(DOMAIN, charge_point_identifier(entry_id, charge_point_id)),
    )
