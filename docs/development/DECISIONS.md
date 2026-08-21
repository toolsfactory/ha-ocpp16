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

**Context:** OCPP's standalone core (`core/`) already has its own push-based, poll-free domain
model — `QueryService`/`CommandService` are free, always-current in-memory reads with no I/O.
`AGENTS.md`'s Home Assistant rule ("entities read `coordinator.data`, never reach past it") is
written for the common case where the coordinator's fetch _is_ the expensive operation worth
sharing across entities. Here it is not: there is nothing to fetch, and nothing to poll
(`iot_class: local_push`).

**Decision:** `OcppCoordinator(DataUpdateCoordinator[StateChangeEvent | None])`,
`update_interval=None`. The coordinator holds only the most recently published `StateChangeEvent`,
not a materialized copy of any domain state. Entities extend `CoordinatorEntity[OcppCoordinator]`
for lifecycle/`available` plumbing and re-render triggers, but read `QueryService`/
`CommandService` directly in their property getters — exactly as they would without a coordinator
at all.

**Rationale:**

- Materializing a second `.data` snapshot from `QueryService` would just be a synchronization
  liability (two copies of the same state, no benefit) with no read ever actually reading it.
- The event still buys the one thing a coordinator is for here: entities that only care about
  their own connector (e.g. `OcppEffectivePowerLimitSensor`) can filter by `event.connector_id`
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

**Context:** `__init__.py` originally constructed `OcppCoordinator` (which subscribes on
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
constructing `OcppCoordinator` in `async_setup_entry()`.

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
`entry.options`, editable via `OcppOptionsFlow` without removing the entry. Changing them fires an
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

**Decision:** Each OCPP entity (`OcppChargePointStateSensor`, `OcppCurrentPowerSensor`,
`OcppEffectivePowerLimitSensor`, `OcppMeasurandSensor`, and the two switches) is its own class with
its own `native_value`/`is_on` logic, sharing only `OcppConnectorEntity` (device info, unique ID,
`available`).

**Rationale:** `value_fn` earns its keep when several entities are otherwise a copy of each other
with a different lookup — that isn't true here. `OcppEffectivePowerLimitSensor` makes its own OCPP
call and caches the result; `OcppMeasurandSensor` is dynamically instantiated per reported
measurand with per-instance unit/device-class resolution; `OcppChargePointStateSensor` maps a raw
OCPP status through a five-value model plus REQ-0035 discovery attributes. Forcing these into one
parameterized class would make the parameterization the complex part.

**Consequences:** Adding a platform-standard `EntityDescription` later (e.g. if OCPP grows several
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

**Context:** `OcppCurrentPowerSensor` overrode `available` to return `False` whenever no matching
`MeterValues` sample had arrived yet — even while the charge point was fully connected and
otherwise healthy. Home Assistant's own convention reserves `unavailable` for "cannot reach the
device at all" and uses `unknown` for "reachable, but no value yet" (state class sensors return
`None` from `native_value` for the latter, which HA renders as `unknown` automatically).

**Decision:** Removed the `available` override; the sensor now falls back to
`OcppConnectorEntity`'s online-only availability check, so it renders `unknown` until the first
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
already relying on per-phase `OcppMeasurandSensor` entities.

**Consequences:** None externally visible beyond the fix itself — this is additive precision, not
a shape change to any existing entity's state or attributes.

---

### Unmapped measurand sensors are disabled by default

**Date:** 2026-08-19

**Context:** `OcppMeasurandSensor` is created dynamically for every measurand a charge point
actually reports, including ones outside `_MEASURAND_META` that OCPP does not recognize well
enough to assign a `device_class`/`state_class` to. Every one of them appeared enabled by default,
regardless of how common or useful it actually is (Quality Scale rule
`entity-disabled-by-default`).

**Decision:** `_attr_entity_registry_enabled_default = measurand in _MEASURAND_META`. The
measurands OCPP already recognizes (energy, power, current, voltage, temperature, state of
charge) stay enabled by default; anything outside that set is registered but disabled, reachable
through the entity registry like any other disabled-by-default entity.

**Rationale:** This is a judgment call, not a precisely specified rule — the alternative would be
hand-picking specific measurands as noisy/diagnostic, which requires knowing in advance what
charge points report, information this project doesn't have. Splitting on "does OCPP already
recognize this measurand" is the least surprising line available: every measurand a typical user
already depends on (the ones with a real unit/device_class) is unaffected, and only genuinely
unknown/unclassified readings default to hidden.

**Consequences:** A charge point reporting a measurand outside `_MEASURAND_META` no longer clutters
the entity list unasked; a user who wants it enables it once via the entity registry. Not a
breaking change — no existing enabled entity becomes disabled, since every measurand that was ever
enabled by default is, by construction, already in `_MEASURAND_META`.

---

### Accepted risk: `charge_point_id` is not redacted in diagnostics

**Date:** 2026-08-19

**Context:** `diagnostics.py` redacts `host`, the authorization-file path, and the default idTag,
but leaves each charge point's `charge_point_id` in plain text. A 2026-08-19 QUALITY_REVIEW.md pass
flagged this — `charge_point_id` is chosen by whoever installs the charge point, not by OCPP, so it
can in principle carry a location, site, or customer name (e.g. `"Garage-Munich-Slot-5"`).

**Decision:** Leave it unredacted. Accepted, not fixed.

**Rationale:** `charge_point_id` is not actually hidden anywhere else in this integration — it is
the literal device name shown throughout the Home Assistant UI (`charge_point_device_info()` sets
`name=f"Charge Point {charge_point_id}"`), visible to anyone with access to **Settings** → **Devices
& Services** already. Redacting it only in the diagnostics export would not meaningfully improve
privacy — the same string is one click away regardless — while it would actively hurt the
diagnostics export's usefulness (harder to match an entry back to the device it describes when
troubleshooting with the developer). This differs from `host`/`authorization_file`/`default_id_tag`,
none of which are ever shown in the UI elsewhere.

**Consequences:** A diagnostics export should still be treated as something to review before
sharing outside the household/installation, the same way a device name or dashboard screenshot
would be — this is about not duplicating an existing, already-visible identifier, not about
diagnostics being free of anything sensitive.

---

### `set_power_limit`/`clear_power_limit` raise on rejection (reversed from the original data-return contract)

**Date:** 2026-08-19

**Context:** REQ-0035 capabilities 3/4 originally returned `{"status": "accepted"|"rejected"|
"not_supported"}` (set) and `{"status": "accepted"|"unknown"}` (clear) as ordinary successful
service data, documented as the stable interop contract for the separate load-management
integration. A 2026-08-19 QUALITY_REVIEW.md pass pointed out the direct consequence: Home Assistant
and any automation checking only for a raised error sees a charge point's outright rejection of a
power-limit change as a successful call, and this data-return shape is what blocks the Silver
Quality Scale rule `action-exceptions` — the same rule the previous round's fix for `reset`/
`unlock_connector`/`change_configuration` satisfied by raising instead.

**Decision:** Confirmed explicitly with the maintainer (this is pre-1.0, where `AGENTS.md`'s own
default is to prefer breaking over compatibility scaffolding): both services now raise
`ServiceValidationError` when the charge point does not respond `"Accepted"`, matching the pattern
already used by every other mutating OCPP service. A successful call still returns
`{"status": "accepted"}` — only the rejection path changed, from data to an exception.

**Rationale:** Consistency with the rest of this integration's service surface outweighs keeping a
contract shape that itself blocks a real Quality Scale rule. Reversing this pre-1.0, while the
separate load-management integration can still absorb the change cheaply, is far less costly than
reversing it later.

**Consequences:** Breaking change to the documented REQ-0035 interop contract — the one thing this
project has been most careful to keep stable for the separate load-management integration all
session. `INTEROP_CONTRACT.md`'s capability 3/4 rows are updated to match. A caller that previously
branched on `result["status"]` must now catch `ServiceValidationError` instead; a caller that only
checked for a raised error to detect failure needs no changes at all.

---

### `ocpp.trigger_message` returns `Rejected`/`NotImplemented` as data, not an exception

**Date:** 2026-08-20

**Context:** `ocpp.trigger_message` (OCPP `TriggerMessage.req`) is not a REQ-0035 contract
capability — it was added alongside the heartbeat sensor and reset/unlock buttons as a separate
scope decision (see "Expose Reset/UnlockConnector/GetConfiguration/ChangeConfiguration as HA
services" above). Confirmed with the maintainer before implementation: unlike `set_power_limit`/
`clear_power_limit`/`reset`/`unlock_connector`/`change_configuration`, its status is returned as
normal response data (`{"status": "Accepted"|"Rejected"|"NotImplemented"}`) even when not
`"Accepted"`, rather than raising `ServiceValidationError`. A subsequent QUALITY_REVIEW.md pass
flagged this as inconsistent with every other mutating service and with the Silver Quality Scale
rule `action-exceptions` — correctly noting that the decision itself was never recorded here, only
in the plan file and the code's own docstrings.

**Decision:** Kept as data-return, not changed to raise. `trigger_message` does not change any
charge-point state the way `reset`/`unlock_connector`/`set_power_limit` do — it only asks the
charge point to resend a message it may not support. A `"Rejected"`/`"NotImplemented"` reply is
informative ("this charge point doesn't support triggering that message"), not a failed mutation,
so treating it as an exception would misrepresent a successful, informative round trip as an error.

**Consequences:** `action-exceptions` is a deliberate, documented deviation for this one service,
not a gap to close — an automation that only checks for a raised error to detect "did the trigger
work" must inspect the returned `status` instead. `INTEROP_CONTRACT.md`'s "outside this contract"
section and `docs/user/CONFIGURATION.md`/`README.md`'s service descriptions already document this
behavior; this entry is the decision record those pages were missing a link to.

---

### Project identity renamed from OCCP to OCPP

**Date:** 2026-08-20

**Context:** The domain (`occp`), class prefix (`Occp`), and title (`OCCP - OCPP 1.6 Central
System`) were never a deliberate distinct brand — they were a mistake from when the project was
first initialized from the blueprint (`initialize.sh --domain occp ...`). The protocol this
integration implements is OCPP (Open Charge Point Protocol); "OCCP" was simply wrong.

**Decision:** Renamed everywhere: domain `occp` → `ocpp`, class prefix `Occp` → `Ocpp`, title to
`OCPP 1.6 Central System` (dropping the now-redundant `OCCP -` prefix), repository references to
`toolsfactory/ocpp-ha`. Mechanical, via a scripted case-sensitive substitution pass across every
tracked file (99 files), not per-file edits — the scale made that the only practical approach.

**Rationale:** Getting the project's own name right matters on its own, and every day this shipped
under the wrong name made the eventual rename more disruptive for real installations. Pre-1.0 is
the cheapest this will ever be.

**Consequences — the largest breaking change of this project's history:**

- **No migration is possible.** Unlike every other breaking change recorded in this document, a
  domain rename is not a data-shape or value change Home Assistant can carry an existing config
  entry through — a config entry belongs permanently to the domain string that created it. Every
  entry loaded under `occp` (including every entry in the development instance used throughout this
  session) is now attached to an integration Home Assistant can no longer find; it must be deleted
  and re-added under `ocpp` from scratch. This is a property of how config entries work, not a gap
  in this project's migration code.
- **A structural naming collision, not a bug:** `ocpp` is now both this project's own domain _and_
  the name of the `ocpp` PyPI library it depends on (`core/ocpp16/` wraps that library
  specifically for OCPP 1.6). This collision surfaced two real, now-fixed tooling bugs rather than
  staying purely cosmetic:
  - `script/develop` used to put `${PWD}/custom_components` on `PYTHONPATH`, making every directory
    inside it directly importable as a bare top-level package by that name. Harmless when nothing
    under `custom_components/` shared a name with a real dependency; actively breaking now, causing
    a spurious "partially initialized module" circular-import error the moment anything imported the
    real `ocpp` library. Fixed by putting the repository root on `PYTHONPATH` instead, so
    `custom_components.ocpp` resolves as a namespace package without shadowing the dependency.
  - `script/clean`'s "uninstall an accidentally self-installed package" cleanup matched by bare
    package name alone (`pip show <domain>`) — safe when nothing under `custom_components/` could
    collide with a real dependency, but now uninstalling the genuine `ocpp` library on every run
    (including the trap `script/test` added earlier this session). Fixed to check for an actual
    `Editable project location` pointing inside this repository before uninstalling anything,
    which is what an accidental self-install actually looks like — a name match alone is not
    enough evidence anymore.

---

## Future Considerations

### State Restoration

**Status:** Not yet implemented

`OcppAvailabilitySwitch`'s `_last_change_status` attribute (the pending `ChangeAvailability`
status) does not survive a Home Assistant restart. Low priority — the connector's actual on/off
state always comes fresh from the charge point's next `StatusNotification`.

### Multi-Connector Charge Points at Scale

**Status:** Supported, not stress-tested

The architecture (one device per connector, dynamic entity creation) has no fixed connector-count
assumption, but has only been exercised against the `ocpp-cp-simulator` with a handful of
connectors per charge point, not a large fleet.

### Porting `core/`'s own test suite

**Status:** Blocked

The standalone core's ~210 tests live in the separate OCPP source repository and are not reachable
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

**Status:** Local assets satisfy the Quality Scale rule; external HACS registration still outstanding

The developer provided a full local brand asset set (`custom_components/ocpp/brand/`:
`icon`/`logo`/`dark_icon`/`dark_logo`, each with an `@2x` variant) during the 2026-08-20 rename
session — `homeassistant.loader.Integration.has_branding` recognizes a local `brand/` folder shipped
inside the integration itself. **These two things are separate and must not be conflated (a prior
version of this entry did):**

- The Quality Scale `brands` rule is evaluated against `Integration.has_branding` — the local
  assets alone already satisfy it. Nothing further is needed for `brands` to be `pass`.
- HACS's own, unrelated `brands` validator (`config/custom_components/hacs/validate/brands.py`,
  confirmed by reading its source) queries the external `https://brands.home-assistant.io/domains.json`
  live registry, which only `home-assistant/brands` PRs update — this is a HACS distribution
  requirement, not a Quality Scale one. `.github/workflows/validate.yml`'s `ignore: brands` line
  works around exactly this gap, and stays in place until that external PR lands.

Submitting to `home-assistant/brands` is a PR against an Open Home Foundation repo, which this
project's own AI policy (`AGENTS.md`) forbids an agent from opening — that submission, and removing
the `ignore: brands` line once it's accepted, remain the developer's to do.
`docs-removal-instructions` (the other half of the original QUALITY_REVIEW.md finding this entry
was created for) was addressed separately in `GETTING_STARTED.md`.

---

## Decision Review

These decisions should be reviewed periodically (suggested: quarterly or when major features are added) to ensure they still serve the integration's needs.
