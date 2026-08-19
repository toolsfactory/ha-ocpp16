# Interop Contract — the load-management integration interface

This document exists for one reason: **a separate Home Assistant integration (load management) is
planned to be built against OCCP**, and needs a stable, documented surface to build against. This
is that surface, as actually implemented in this repository today.

## Provenance

OCCP's code comments throughout `sensor/`, `switch/`, `service_actions/`, and `utils/interop.py`
reference `REQ-0035`, `ADR-0010`, and a document called `interop-contract.md` as the source of
truth for this contract. **That document does not exist anywhere in this repository** — it lives
(or lived) only in OCCP's original standalone source repository, which this repository imported
code from but not its requirements/ADR documentation. This file is the as-implemented record of
that contract for the Home Assistant layer specifically, reconstructed from the code and its
comments. If the canonical `interop-contract.md` becomes available, reconcile this document
against it — this one is not a substitute for that source of truth, only a working stand-in.

## How to consume this contract

**There is no shared code, and there should not be.** The integration boundary is Home Assistant
itself: entity states/attributes, the device registry, and services. A load-management integration
reads OCCP's sensors and calls OCCP's services exactly like a dashboard or automation would —
nothing here requires importing anything from `custom_components.occp`.

## Self-description: read `supported_capabilities` first

Every charge point's status sensor (`OccpChargePointStateSensor`, capability 2 below) exposes a
`supported_capabilities` attribute — an integer bitmask. **A load-management integration should
read this at runtime rather than hardcoding which capabilities are available.** OCCP currently
always reports `127` (capabilities 1–6 and 8; see the table), but the bitmask exists so a consumer
built against this contract keeps working if a future OCCP version — or a different Central System
implementation speaking the same contract — offers a different subset.

```text
Bit   Capability
  1   1 — Current power
  2   2 — State
  4   3 — Set power limit
  8   4 — Clear power limit
 16   5 — Read effective power limit
 32   6 — Availability
 64   8 — Authorize idTag
128   9 — Start/release (never offered by OCCP — see "Capability 9" below)
```

There is no bit for capability 7 — it is not a controllable feature but the discovery mechanism
itself (the bitmask and the `min_power_limit_w`/`max_power_limit_w`/`supported_phases` attributes
described below).

## Addressing a charge point or connector

**Never construct an `entity_id` string directly** — a user can rename any entity, and the
project's own rule (`AGENTS.md`) is that identifiers must go through the registries, not
human-editable strings. Resolve through the identifiers below instead, exactly as this project's
own test suite does (`homeassistant.helpers.entity_registry.async_get_entity_id`).

- **Charge point device:** identifier `(DOMAIN, charge_point_id)` = `("occp", "CP001")`. `DOMAIN`
  is `"occp"`.
- **Connector device:** identifier `(DOMAIN, f"{charge_point_id}_{connector_id}")` =
  `("occp", "CP001_1")`. `connectorId` `0` (the charge point as a whole, per OCPP 1.6) never gets
  its own device — there are no capability-1/5/6 entities for it.
- **Entity `unique_id`:** `{entry_id}:{len(charge_point_id)}:{charge_point_id}:{connector_id}_{entity_key}`
  — `entry_id` is the owning config entry's ID (a ULID, never contains `:`), the length-prefixed
  `charge_point_id` makes the split unambiguous regardless of its content, and `entity_key` is
  listed per capability below. Do not construct this string by hand — resolve through the device
  registry (see below) and the entity registry
  (`async_get_entity_id(platform, DOMAIN, unique_id)`), then read `hass.states.get(entity_id)`.
  This shape is a breaking change from an earlier `{charge_point_id}_{connector_id}_{entity_key}`
  scheme that could collide across config entries or ambiguous `charge_point_id` values — see
  [DECISIONS.md](./DECISIONS.md).
- **Service `device_id`:** resolve a device via the device registry the same way, then pass its
  registry `id` (not the domain identifier tuple) as the service's `device_id` field.

A load-management integration typically discovers charge points by listing devices owned by
OCCP's config entries (`device_registry.devices.get_devices_for_config_entry_id()` per entry, or
by filtering on `identifiers` containing `(DOMAIN, ...)`), then resolves each connector's entities
from there.

## Capability table

| #   | Bit | Name                       | HA surface                                       | Notes                                                                                                                                                                                                                                        |
| --- | --- | -------------------------- | ------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | 1   | Current power              | `sensor`, `entity_key="current_power_w"`         | Watts. **`unknown`** (not `0`) until a matching `Power.Active.Import` measurand has actually been reported.                                                                                                                                  |
| 2   | 2   | State                      | `sensor`, `entity_key="charge_point_state"`      | Five-value state (`not_connected`/`ready`/`charging`/`unavailable`/`error`) — see [State mapping](#state-mapping). Carries the discovery attributes (capability 7).                                                                          |
| 3   | 4   | Set power limit            | service `occp.set_power_limit`                   | `{device_id, limit_w, phases?}` → connector device. `{"status": "accepted"\|"rejected"\|"not_supported"}`.                                                                                                                                   |
| 4   | 8   | Clear power limit          | service `occp.clear_power_limit`                 | `{device_id}` → connector device. `{"status": "accepted"\|"unknown"}`.                                                                                                                                                                       |
| 5   | 16  | Read effective power limit | `sensor`, `entity_key="effective_power_limit_w"` | Watts, read back from the charge point via `GetCompositeSchedule`. **`unknown`** (not `0`) until the first successful read; only refreshes on a connector-scoped event, so it can lag a `set_power_limit` call until the next status update. |
| 6   | 32  | Availability               | `switch`, `entity_key="availability"`            | `on` = operative, `off` = inoperative. A `"Scheduled"` `ChangeAvailability` response does **not** flip the switch state immediately — see [Scheduled availability changes](#scheduled-availability-changes).                                 |
| 7   | —   | Discovery                  | Attributes on the capability-2 sensor            | `supported_capabilities` (bitmask, above), `raw_ocpp_status`, `error_code`, `min_power_limit_w`, `max_power_limit_w` (always `null` — OCPP 1.6 has no generic query for these), `supported_phases` (always `[1, 2, 3]`).                     |
| 8   | 64  | Authorize idTag            | service `occp.authorize_id_token`                | `{charge_point_id, id_token}` — no device resolution, addresses the charge point by ID directly. `{"authorized": bool, "status": "accepted"\|"blocked"\|"expired"\|"invalid"}`. OCCP's authorization provider never returns `"unknown"`.     |
| 9   | 128 | Start/release              | **not offered**                                  | See below.                                                                                                                                                                                                                                   |

### State mapping

Raw OCPP 1.6 connector status → the five-value model:

| Raw OCPP status                                          | Mapped state    |
| -------------------------------------------------------- | --------------- |
| `Available`                                              | `not_connected` |
| `Preparing`, `SuspendedEVSE`, `SuspendedEV`, `Finishing` | `ready`         |
| `Charging`                                               | `charging`      |
| `Reserved`, `Unavailable`                                | `unavailable`   |
| `Faulted`                                                | `error`         |

The raw status is still available verbatim in the `raw_ocpp_status` attribute for anything that
needs OCPP-level granularity beyond the five-value model.

### Scheduled availability changes

`ChangeAvailability` can return `"Scheduled"` when a connector has an active transaction — the
charge point defers the change until charging stops. OCCP surfaces this as
`last_change_status: "Scheduled"` and `change_pending: true` on the availability switch's
attributes, but the switch's actual `on`/`off` **state comes exclusively from the next
`StatusNotification`**, never synthesized from the `ChangeAvailability` response. A
load-management integration that calls `occp.change_configuration`-adjacent availability changes
should watch for `change_pending` clearing (or the state itself flipping), not assume the change
already took effect.

### Capability 9 — not offered

OCCP never sets bit `128`. There is no "start/release" service or entity, and none is planned as
part of this contract — this is an explicit non-goal (`REQ-0020` Non-Goals in the code comments),
not an oversight. A load-management integration must not assume this capability exists just
because 1–6 and 8 do; it should check the bitmask.

## Services and entities outside this contract

`occp.reset`, `occp.unlock_connector`, `occp.get_configuration`, and `occp.change_configuration`
exist (see the main [README](../../README.md)) but are **not** part of the numbered capability
contract above — they were added as a separate scope decision (see `DECISIONS.md`) because the
underlying OCPP calls already existed in `core/`, not because REQ-0035 calls for them. A
load-management integration can use them, but should not treat their presence as guaranteed the
way it can for capabilities 1–6 and 8.

The same applies to the `active_phases` sensor (`sensor`, `entity_key="active_phases"`): state is
the count of currently-active phases (a `Current.Import` sample above zero), with per-phase
readings (`phase_l1_a`/`phase_l2_a`/`phase_l3_a`) as attributes. It is a convenience entity, not a
REQ-0035 capability — a load-management integration wanting per-phase current for its own logic
should read this sensor's attributes directly rather than expecting a bitmask entry for it.

## Stability

- **`unique_id` shape, `entity_key` names, service names, and service schemas are the stable
  contract.** Changing any of them is a breaking change under this project's own rules
  (`AGENTS.md`'s "Breaking changes — warn before implementing") and requires the same warn-first
  process as any other entity ID/service signature change, plus an update to this document.
- **`entity_id` strings, device names, and friendly names are not stable** — users can rename any
  of them. Always resolve through the registries (see "Addressing a charge point or connector").
- **The bitmask is the authoritative "what's available" signal**, not this document's capability
  table by itself — if OCCP's `SUPPORTED_CAPABILITIES` ever changes, this table is updated to
  match, but a consumer that reads the bitmask at runtime does not need to wait for that update to
  behave correctly.

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md) — how this contract's services/entities are wired
  internally (`utils/interop.py` is the adapter module implementing capabilities 1, 3, 4, 5, and 8).
- [DECISIONS.md](./DECISIONS.md) — why the four non-contract services exist, and other
  architectural decisions.
- [README.md](../../README.md) — the end-user-facing entity and service reference.
