# Architectural and Design Decisions

This document records significant architectural and design decisions made during the development of this integration.

## Format

Each decision is documented with:

- **Date:** When the decision was made
- **Context:** Why this decision was necessary
- **Decision:** What was decided
- **Rationale:** Why this approach was chosen
- **Consequences:** Expected impacts and trade-offs

> [!NOTE]
> Guidance on _when_ a decision is worth recording here, and a copy-ready entry template, lives in the
> [`ha-planning`](../../.agents/skills/ha-planning/SKILL.md) agent skill.

---

## Decision Log

### Thin coordinator: hold the last event, not a data snapshot

**Date:** 2026-08-18

**Context:** OCCP's standalone core (`core/`) already has its own push-based, poll-free domain
model — `QueryService`/`CommandService` are free, always-current in-memory reads with no I/O.
`AGENTS.md`'s Home Assistant rule ("entities read `coordinator.data`, never reach past it") is
written for the common case where the coordinator's fetch _is_ the expensive operation worth
sharing across entities. Here it is not: there is nothing to fetch, and nothing to poll
(`iot_class: local_push`).

**Decision:** `OccpCoordinator(DataUpdateCoordinator[StateChangeEvent | None])`,
`update_interval=None`. The coordinator holds only the most recently published `StateChangeEvent`,
not a materialized copy of any domain state. Entities extend `CoordinatorEntity[OccpCoordinator]`
for lifecycle/`available` plumbing and re-render triggers, but read `QueryService`/
`CommandService` directly in their property getters — exactly as they would without a coordinator
at all.

**Rationale:**

- Materializing a second `.data` snapshot from `QueryService` would just be a synchronization
  liability (two copies of the same state, no benefit) with no read ever actually reading it.
- The event still buys the one thing a coordinator is for here: entities that only care about
  their own connector (e.g. `OccpEffectivePowerLimitSensor`) can filter by `event.connector_id`
  before doing an OCPP round trip (`GetCompositeSchedule`), instead of refreshing on every event
  for every connector.
- Confirmed explicitly with the maintainer as a deliberate, narrower reading of the "coordinator
  data only" rule rather than the "thick" alternative (copy every read into `.data`).

**Consequences:**

- A future contributor reading `AGENTS.md`'s rule literally may expect entities to read
  `coordinator.data` for their values — they do not, by design. This document and
  `ARCHITECTURE.md`'s "Push, not poll" section exist specifically so that surprise resolves
  quickly instead of triggering an incorrect "fix".
- `coordinator.async_add_listener()` is still the mechanism `_SensorManager`/`_SwitchManager` use
  to detect newly-appeared connectors/measurands — only what each listener _does_ with the event
  differs from the polling-coordinator default.

---

### Device-registration listener must subscribe before the coordinator

**Date:** 2026-08-18

**Context:** `__init__.py` originally constructed `OccpCoordinator` (which subscribes on
`app.query_service`) before subscribing its own charge-point device-registration listener.
`EventBus.publish()` calls listeners in subscription order, and
`DataUpdateCoordinator.async_set_updated_data()` triggers the coordinator's _own_ listeners
(`_SensorManager`/`_SwitchManager`, which create connector devices with `via_device` pointing at
the charge-point device) synchronously, inside that same call. On a charge point's very first
event this meant a connector device could be registered before its parent charge-point device
existed — a `homeassistant.helpers.frame` deprecation warning, not a hard error, so it went
unnoticed through several rounds of `--level error`-only log checks until a coordinator/entity
test caught it directly.

**Decision:** Subscribe the device-registration listener on `app.query_service` before
constructing `OccpCoordinator` in `async_setup_entry()`.

**Rationale:** Subscription order is the only lever available — `EventBus` has no priority
concept, and adding one for a single ordering dependency would be over-engineering for a
project this size.

**Consequences:** Anyone adding a third `app.query_service.subscribe()` call in `__init__.py`
that depends on the device registry needs to keep it ahead of the coordinator too; anyone adding
one that does not depend on it can go anywhere.

---

### `unique_id` is a random UUID, not host:port

**Date:** 2026-08-17

**Context:** The config flow originally used `host:port` as the config entry's `unique_id` and
relied on `_abort_if_unique_id_configured()` to reject duplicates. `AGENTS.md`'s project rule is
explicit: a unique ID must be a serial number, MAC, device ID, or account ID — never a network
address, since addresses can change or be reused across genuinely different setups.

**Decision:** `unique_id = str(uuid4())`, generated once at entry creation. Duplicate
host:port combinations are now caught explicitly via `_host_port_already_configured()` (a plain
scan of `self._async_current_entries()` comparing `entry.data`), instead of relying on
`unique_id`.

**Consequences:** The duplicate-detection logic is now bespoke instead of the standard
`_abort_if_unique_id_configured()` helper — documented at the call site in
`config_flow_handler/config_flow.py` so it isn't mistaken for an oversight.

---

### `entry.data` vs. `entry.options`: only connection-critical fields in `data`

**Date:** 2026-08-17

**Context:** The listen host/port are needed to establish the WebSocket server and cannot be
changed without disruption; the authorization file path and default idTag are operational
settings a user may reasonably want to change without recreating the entry.

**Decision:** `host`/`port` live in `entry.data`. `authorization_file`/`default_id_tag` live in
`entry.options`, editable via `OccpOptionsFlow` without removing the entry. Changing them fires an
options-update listener that reloads the entry (`CentralSystemApp` builds both from the loaded
config once, at setup).

**Consequences:** Entries created before this change needed a migration
(`VERSION 1` → `MINOR_VERSION 2`, `async_migrate_entry()` moves the two option-shaped keys from
`data` to `options`).

---

### Expose Reset/UnlockConnector/GetConfiguration/ChangeConfiguration as HA services

**Date:** 2026-08-17

**Context:** `core/`'s `CommandService` and the standalone console already supported these four
OCPP calls, but only the three REQ-0035 interop-contract capabilities
(`set_power_limit`/`clear_power_limit`/`authorize_id_token`) were exposed as Home Assistant
services. This is a scope decision, not a REQ-0035 requirement — the interop contract does not
call for these four (see [INTEROP_CONTRACT.md](./INTEROP_CONTRACT.md)); a separate load-management
integration should not expect them to be part of that stable surface.

**Decision:** Add `reset`, `unlock_connector`, `get_configuration`, `change_configuration` as
ordinary Home Assistant services, following the same `ServiceValidationError`-on-bad-input pattern
as the three interop services.

**Rationale:** These are useful operational actions (remote reset, connector unlock, reading/
writing OCPP configuration keys) that already existed one layer down; not exposing them would have
meant reimplementing them later for no reason.

**Consequences:** `reset`/`get_configuration`/`change_configuration` target the charge-point
device itself; `unlock_connector` targets a connector device — the two device-scoped resolvers in
`service_actions/_resolvers.py` reject the wrong kind of device explicitly rather than silently
misrouting the call.

---

### No `EntityDescription`/`value_fn` pattern

**Date:** 2026-08-18 (documented; the entities themselves predate the restructuring)

**Context:** The blueprint template's usual sensor pattern is a shared entity class parameterized
by an `EntityDescription.value_fn` per logical group, with per-group files holding descriptions
only (see `ha-entity-platform`).

**Decision:** Each OCCP entity (`OccpChargePointStateSensor`, `OccpCurrentPowerSensor`,
`OccpEffectivePowerLimitSensor`, `OccpMeasurandSensor`, and the two switches) is its own class with
its own `native_value`/`is_on` logic, sharing only `OccpConnectorEntity` (device info, unique ID,
`available`).

**Rationale:** `value_fn` earns its keep when several entities are otherwise a copy of each other
with a different lookup — that isn't true here. `OccpEffectivePowerLimitSensor` makes its own OCPP
call and caches the result; `OccpMeasurandSensor` is dynamically instantiated per reported
measurand with per-instance unit/device-class resolution; `OccpChargePointStateSensor` maps a raw
OCPP status through a five-value model plus REQ-0035 discovery attributes. Forcing these into one
parameterized class would make the parameterization the complex part.

**Consequences:** Adding a platform-standard `EntityDescription` later (e.g. if OCCP grows several
genuinely interchangeable sensors) is still open — this decision only covers the entities that
exist today.

---

### Entry-scoped device/entity identifiers, length-prefixed

**Date:** 2026-08-19

**Context:** `connector_identifier()` originally built device identifiers and entity `unique_id`s
as `f"{charge_point_id}_{connector_id}"`, with no per-config-entry component. This collided in two
ways: `charge_point_id="station_1"` connector 0 and `charge_point_id="station"` connector 1
produced the same string, and two config entries that happened to see the same OCPP
`chargePointId` (e.g. two independent simulators both booting as `CP001`) produced literally
identical device identifiers, so the second entry's device silently merged into the first's in the
device registry, and its service calls routed to whichever entry the device registry entry
happened to point at.

**Decision:** Identifiers are now `f"{entry_id}:{len(charge_point_id)}:{charge_point_id}:{connector_id}"`
(the charge-point device drops the trailing `:{connector_id}`). Length-prefixing `charge_point_id`
makes the split provably unambiguous regardless of what characters a charge point's ID contains — a
plain extra separator would only make collisions less likely, not impossible. `entry_id` is a
fixed-format ULID that structurally cannot contain `:`, so splitting off the first `:`-delimited
segment is always safe.

**Rationale:** Correctness over a plain separator scheme, and scoping by `entry_id` closes the
cross-instance collision entirely rather than just making it rare. Service action resolution
(`service_actions/_resolvers.py`) now scopes through `DeviceEntry.config_entry_id` for the same
reason — device identity, not `charge_point_id` string matching, decides which entry a call
belongs to.

**Consequences:** Breaking change, shipped without a migration (pre-1.0, per `AGENTS.md`'s own
default) — existing devices/entities from before this change become orphaned and need manual
removal after upgrading. `authorize_id_token` initially remained the one service that still
resolved by bare `charge_point_id` (it takes no device) and so retained the residual
cross-instance ambiguity this decision otherwise closes. Resolved 2026-08-19: an optional
`device_id` field was added to the service (additive, not a schema break) — when present it
resolves the entry the same way every other service does; when absent, the original scan-based
behavior is unchanged, so callers who need disambiguation now have a way to get it.

---

### `current_power_w` reports `unknown`, not `unavailable`, before the first sample

**Date:** 2026-08-19

**Context:** `OccpCurrentPowerSensor` overrode `available` to return `False` whenever no matching
`MeterValues` sample had arrived yet — even while the charge point was fully connected and
otherwise healthy. Home Assistant's own convention reserves `unavailable` for "cannot reach the
device at all" and uses `unknown` for "reachable, but no value yet" (state class sensors return
`None` from `native_value` for the latter, which HA renders as `unknown` automatically).

**Decision:** Removed the `available` override; the sensor now falls back to
`OccpConnectorEntity`'s online-only availability check, so it renders `unknown` until the first
`Power.Active.Import` sample is reported.

**Rationale:** Matches HA convention and what an automation author expects: `unavailable` should
mean "something is wrong," not "this specific measurand hasn't been reported in this session yet."

**Consequences:** Breaking change — a state-value change for anyone with automations or dashboards
keyed on `unavailable` for this entity. Shipped together with the identifier-scheme break above so
both land under one `BREAKING CHANGE:` release note instead of two.

---

### Meter-value store keys samples by `(measurand, phase)`, not bare `measurand`

**Date:** 2026-08-19

**Context:** `MeterValueStore` indexed the latest sample per connector/transaction by the bare
OCPP `measurand` string. A three-phase `MeterValues` report sends one `sampledValue` entry per
phase for the same measurand (e.g. `Current.Import` for L1, L2, L3) — each subsequent phase's
sample overwrote the previous one under the same key, so only the last-processed phase's value was
ever retained.

**Decision:** `_by_connector`/`_by_transaction` are now keyed by `(measurand, phase)`, with
`phase=None` reserved for a measurand reported without per-phase breakdown (e.g. a single combined
total).

**Rationale:** This is what made the new Active Phases sensor possible at all — it reads all three
phases' `Current.Import` samples independently — and it was silently losing L1/L2 data for anyone
already relying on per-phase `OccpMeasurandSensor` entities.

**Consequences:** None externally visible beyond the fix itself — this is additive precision, not
a shape change to any existing entity's state or attributes.

---

### Unmapped measurand sensors are disabled by default

**Date:** 2026-08-19

**Context:** `OccpMeasurandSensor` is created dynamically for every measurand a charge point
actually reports, including ones outside `_MEASURAND_META` that OCCP does not recognize well
enough to assign a `device_class`/`state_class` to. Every one of them appeared enabled by default,
regardless of how common or useful it actually is (Quality Scale rule
`entity-disabled-by-default`).

**Decision:** `_attr_entity_registry_enabled_default = measurand in _MEASURAND_META`. The
measurands OCCP already recognizes (energy, power, current, voltage, temperature, state of
charge) stay enabled by default; anything outside that set is registered but disabled, reachable
through the entity registry like any other disabled-by-default entity.

**Rationale:** This is a judgment call, not a precisely specified rule — the alternative would be
hand-picking specific measurands as noisy/diagnostic, which requires knowing in advance what
charge points report, information this project doesn't have. Splitting on "does OCCP already
recognize this measurand" is the least surprising line available: every measurand a typical user
already depends on (the ones with a real unit/device_class) is unaffected, and only genuinely
unknown/unclassified readings default to hidden.

**Consequences:** A charge point reporting a measurand outside `_MEASURAND_META` no longer clutters
the entity list unasked; a user who wants it enables it once via the entity registry. Not a
breaking change — no existing enabled entity becomes disabled, since every measurand that was ever
enabled by default is, by construction, already in `_MEASURAND_META`.

---

## Future Considerations

### State Restoration

**Status:** Not yet implemented

`OccpAvailabilitySwitch`'s `_last_change_status` attribute (the pending `ChangeAvailability`
status) does not survive a Home Assistant restart. Low priority — the connector's actual on/off
state always comes fresh from the charge point's next `StatusNotification`.

### Multi-Connector Charge Points at Scale

**Status:** Supported, not stress-tested

The architecture (one device per connector, dynamic entity creation) has no fixed connector-count
assumption, but has only been exercised against the `ocpp-cp-simulator` with a handful of
connectors per charge point, not a large fleet.

### Porting `core/`'s own test suite

**Status:** Blocked

The standalone core's ~210 tests live in the separate OCCP source repository and are not reachable
from this devcontainer. Tracked, not attempted.

### Removing stale charge-point devices

**Status:** Deferred — no business rule decided yet

A charge point that connects once and then disappears permanently (replaced, decommissioned,
reconfigured to talk to a different Central System) leaves its device and entities behind forever
— nothing in `__init__.py` ever removes a device once `_register_device` has created it. Fixing
this needs a decision only the developer can make first: what counts as "permanently gone" (manual
removal only vs. an automatic time-based rule, and if automatic, after how long with no
reconnect) — a decision explicitly deferred rather than guessed at during the 2026-08-19
QUALITY_REVIEW.md pass. Until that's decided, a charge point that will never come back needs manual
removal via the device page in **Settings** → **Devices & Services**.

### CI does not gate on type-check or tests

**Status:** Blocked — environment permission, not a project decision

`.github/workflows/lint.yml` only runs `script/lint-check`; `script/type-check` and `script/test`
are not required CI jobs, so a type or runtime regression can merge despite green CI. Both the
2026-08-18 and 2026-08-19 QUALITY_REVIEW.md passes flagged this, and both times the fix was
identical and ready to apply — two new jobs mirroring the existing `ruff` job's
checkout/Python/uv/cache setup, running `script/type-check` and `script/test` in place of
`script/lint-check` — but the acting agent's permission settings deny writes to
`.github/workflows/` in this environment. The developer needs to either apply this change directly
or grant that access.

### Brand assets

**Status:** Deferred — outside this project's authority to do autonomously

No local brand assets exist, and the Quality Scale `brands` rule requires submitting icon/logo
assets to the external `home-assistant/brands` repository — a PR against an Open Home Foundation
repo, which this project's own AI policy (`AGENTS.md`) forbids an agent from opening. Needs real
artwork and a manually submitted PR from the developer; `docs-removal-instructions` (the other half
of the same QUALITY_REVIEW.md finding) was addressed separately in `GETTING_STARTED.md`.

---

## Decision Review

These decisions should be reviewed periodically (suggested: quarterly or when major features are added) to ensure they still serve the integration's needs.
