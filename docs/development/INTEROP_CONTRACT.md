# Interop Contract — the load-management integration interface

This document exists for one reason: **a separate Home Assistant integration (load management) is
planned to be built against OCPP**, and needs a stable, documented surface to build against. This
is that surface, as actually implemented in this repository today.

## Provenance

OCPP's code comments throughout `sensor/`, `switch/`, `service_actions/`, and `utils/interop.py`
reference `REQ-0035`, `ADR-0010`, and a document called `interop-contract.md` as the source of
truth for this contract. **That document does not exist anywhere in this repository** — it lives
(or lived) only in OCPP's original standalone source repository, which this repository imported
code from but not its requirements/ADR documentation. This file is the as-implemented record of
that contract for the Home Assistant layer specifically, reconstructed from the code and its
comments. If the canonical `interop-contract.md` becomes available, reconcile this document
against it — this one is not a substitute for that source of truth, only a working stand-in.

## How to consume this contract

**There is no shared code, and there should not be.** The integration boundary is Home Assistant
itself: entity states/attributes, the device registry, and services. A load-management integration
reads OCPP's sensors and calls OCPP's services exactly like a dashboard or automation would —
nothing here requires importing anything from `custom_components.ocpp16`.

## Self-description: read `supported_capabilities` first

Every charge point's status sensor (`Ocpp16ChargePointStateSensor`, capability 2 below) exposes a
`supported_capabilities` attribute — an integer bitmask. **A load-management integration should
read this at runtime rather than hardcoding which capabilities are available.** OCPP currently
always reports `127` (capabilities 1–6 and 8; see the table), but the bitmask exists so a consumer
built against this contract keeps working if a future OCPP version — or a different Central System
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
128   9 — Start/release (never offered by OCPP — see "Capability 9" below)
```

There is no bit for capability 7 — it is not a controllable feature but the discovery mechanism
itself (the bitmask and the `min_power_limit_w`/`max_power_limit_w`/`supported_phases` attributes
described below).

## Addressing a charge point or connector

**Never construct an `entity_id` string directly** — a user can rename any entity, and the
project's own rule (`AGENTS.md`) is that identifiers must go through the registries, not
human-editable strings. Resolve through the identifiers below instead, exactly as this project's
own test suite does (`homeassistant.helpers.entity_registry.async_get_entity_id`).

- **Charge point device:** identifier `(DOMAIN, charge_point_identifier(entry_id, charge_point_id))`
  = `(DOMAIN, f"{entry_id}:{charge_point_id}")`, e.g. `("ocpp16", "01ABC...:CP001")`. `DOMAIN` is
  `"ocpp16"`; `entry_id` is the owning config entry's ID — like the entity `unique_id` below, this
  identifier is entry-scoped, not just `charge_point_id` alone, so two instances that happen to see
  the same `chargePointId` never collide. Build it with
  [`entity_utils/device.py`](../../custom_components/ocpp16/entity_utils/device.py)'s
  `charge_point_identifier()`, never by hand.
- **Connector device:** identifier
  `(DOMAIN, connector_identifier(entry_id, charge_point_id, connector_id))` =
  `(DOMAIN, f"{entry_id}:{len(charge_point_id)}:{charge_point_id}:{connector_id}")`, e.g.
  `("ocpp16", "01ABC...:5:CP001:1")` — the same length-prefixing as the entity `unique_id` below, for
  the same reason. Build it with `entity_utils/device.py`'s `connector_identifier()`.
  `connectorId` `0` (the charge point as a whole, per OCPP 1.6) never gets its own device — there
  are no capability-1/5/6 entities for it.
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
OCPP's config entries (`device_registry.devices.get_devices_for_config_entry_id()` per entry, or
by filtering on `identifiers` containing `(DOMAIN, ...)`), then resolves each connector's entities
from there.

## Capability table

| #   | Bit | Name                       | HA surface                                       | Notes                                                                                                                                                                                                                                                                                                                                                                                             |
| --- | --- | -------------------------- | ------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | 1   | Current power              | `sensor`, `entity_key="current_power_w"`         | Watts. **`unknown`** (not `0`) until a matching `Power.Active.Import` measurand has actually been reported.                                                                                                                                                                                                                                                                                       |
| 2   | 2   | State                      | `sensor`, `entity_key="charge_point_state"`      | Five-value state (`not_connected`/`ready`/`charging`/`unavailable`/`error`) — see [State mapping](#state-mapping). Carries the discovery attributes (capability 7).                                                                                                                                                                                                                               |
| 3   | 4   | Set power limit            | service `ocpp16.set_power_limit`                 | `{device_id, limit_w, phases?}` → connector device. Success returns `{"status": "accepted"}`; a `"rejected"`/`"not_supported"` outcome raises `ServiceValidationError` instead of returning that status as data (breaking change, 2026-08-19 — see [DECISIONS.md](./DECISIONS.md)).                                                                                                               |
| 4   | 8   | Clear power limit          | service `ocpp16.clear_power_limit`               | `{device_id}` → connector device. Success returns `{"status": "accepted"}`; an `"unknown"` outcome (no matching profile to clear) raises `ServiceValidationError` the same way.                                                                                                                                                                                                                   |
| 5   | 16  | Read effective power limit | `sensor`, `entity_key="effective_power_limit_w"` | Watts, read back from the charge point via `GetCompositeSchedule`. **`unknown`** (not `0`) until the first successful read; only refreshes on a connector-scoped event, so it can lag a `set_power_limit` call until the next status update.                                                                                                                                                      |
| 6   | 32  | Availability               | `switch`, `entity_key="availability"`            | `on` = operative, `off` = inoperative. A `"Scheduled"` `ChangeAvailability` response does **not** flip the switch state immediately — see [Scheduled availability changes](#scheduled-availability-changes).                                                                                                                                                                                      |
| 7   | —   | Discovery                  | Attributes on the capability-2 sensor            | `supported_capabilities` (bitmask, above), `raw_ocpp_status`, `error_code`, `min_power_limit_w`, `max_power_limit_w` (always `null` — OCPP 1.6 has no generic query for these), `supported_phases` (always `[1, 2, 3]`).                                                                                                                                                                          |
| 8   | 64  | Authorize idTag            | service `ocpp16.authorize_id_token`              | `{charge_point_id, id_token, device_id?}` — `charge_point_id` alone is ambiguous if two loaded instances happen to see the same `chargePointId`; the optional `device_id` (charge point's or a connector's device) disambiguates which instance to query. `{"authorized": bool, "status": "accepted"\|"blocked"\|"expired"\|"invalid"}`. OCPP's authorization provider never returns `"unknown"`. |
| 9   | 128 | Start/release              | **not offered**                                  | See below.                                                                                                                                                                                                                                                                                                                                                                                        |

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
charge point defers the change until charging stops. OCPP surfaces this as
`last_change_status: "Scheduled"` and `change_pending: true` on the availability switch's
attributes, but the switch's actual `on`/`off` **state comes exclusively from the next
`StatusNotification`**, never synthesized from the `ChangeAvailability` response. A
load-management integration that calls `ocpp16.change_configuration`-adjacent availability changes
should watch for `change_pending` clearing (or the state itself flipping), not assume the change
already took effect.

### Capability 9 — not offered

OCPP never sets bit `128`. There is no "start/release" service or entity, and none is planned as
part of this contract — this is an explicit non-goal (`REQ-0020` Non-Goals in the code comments),
not an oversight. A load-management integration must not assume this capability exists just
because 1–6 and 8 do; it should check the bitmask.

## Services and entities outside this contract

`ocpp16.reset`, `ocpp16.unlock_connector`, `ocpp16.get_configuration`, `ocpp16.change_configuration`,
`ocpp16.trigger_message`, and `ocpp16.get_diagnostics` exist (see the main
[README](../../README.md)) but are **not** part of the numbered capability contract above — they
were added as a separate scope decision (see `DECISIONS.md`) because the underlying OCPP calls
already existed in `core/`, not because REQ-0035 calls for them. A load-management integration can
use them, but should not treat their presence as guaranteed the way it can for capabilities 1–6
and 8. The `button` entities (`button.reset`/`button.unlock_connector`) are dashboard-idiomatic
wrappers around `ocpp16.reset`(`"Soft"`)/`ocpp16.unlock_connector` and carry the same status.

The same applies to the `active_phases` sensor (`sensor`, `entity_key="active_phases"`): state is
the count of currently-active phases (a `Current.Import` sample above zero), with per-phase
readings (`phase_l1_a`/`phase_l2_a`/`phase_l3_a`) as attributes. It is a convenience entity, not a
REQ-0035 capability — a load-management integration wanting per-phase current for its own logic
should read this sensor's attributes directly rather than expecting a bitmask entry for it. The
same is true of the `last_heartbeat` sensor (no REQ-0035 capability tracks heartbeat timing).

`number.power_limit_w` is UI convenience over Fähigkeit 3/4 (`ocpp16.set_power_limit`/
`ocpp16.clear_power_limit`), not a new capability of its own — it calls the same
`utils/interop.py` functions the services do. Its `native_value` is optimistic (the last
successfully set/cleared value this session, restored across a HA restart via `RestoreNumber` —
see `DECISIONS.md`), not a live re-read — a load-management integration that needs the charge
point's actual current limit should keep using the `effective_power_limit_w` sensor (capability
5), not this entity's state.

The five session/connection diagnostic sensors added 2026-08-21 are the same kind of convenience,
not new capabilities: `last_transaction_id`, `session_duration_s`, and `session_energy_wh`
(`sensor`, connector-scoped) reflect the connector's most recent transaction — active or already
stopped — via the new `QueryService.get_last_transaction()` read path; `last_stop_reason`
(`sensor`, connector-scoped) is the raw OCPP `Reason` string from that same transaction, not
schema-restricted (real devices aren't always spec-perfect); `reconnect_count` (`sensor`,
charge-point-scoped, `EntityCategory.DIAGNOSTIC`) counts WebSocket (re)connections since process
start, including REQ-0001 AC4 takeovers. None of these are REQ-0035 capabilities and none carry a
bitmask entry.

## Stability

- **`unique_id` shape, `entity_key` names, service names, and service schemas are the stable
  contract.** Changing any of them is a breaking change under this project's own rules
  (`AGENTS.md`'s "Breaking changes — warn before implementing") and requires the same warn-first
  process as any other entity ID/service signature change, plus an update to this document.
- **`entity_id` strings, device names, and friendly names are not stable** — users can rename any
  of them. Always resolve through the registries (see "Addressing a charge point or connector").
- **The bitmask is the authoritative "what's available" signal**, not this document's capability
  table by itself — if OCPP's `SUPPORTED_CAPABILITIES` ever changes, this table is updated to
  match, but a consumer that reads the bitmask at runtime does not need to wait for that update to
  behave correctly.

## Related documents

- [ARCHITECTURE.md](./ARCHITECTURE.md) — how this contract's services/entities are wired
  internally (`utils/interop.py` is the adapter module implementing capabilities 1, 3, 4, 5, and 8).
- [DECISIONS.md](./DECISIONS.md) — why the four non-contract services exist, and other
  architectural decisions.
- [README.md](../../README.md) — the end-user-facing entity and service reference.
