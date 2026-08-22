# Architecture Overview

This document describes the technical architecture of the OCPP 1.6 Central System custom component for Home Assistant.

## Two layers, one hard rule

OCPP is two things wearing one HACS repository:

1. **`custom_components/ocpp16/core/`** — a standalone OCPP 1.6 Central System. WebSocket transport,
   protocol handlers, and an in-memory domain model (registry, connector state, transactions, meter
   values). It has **zero `homeassistant.*` imports**, can run on its own
   (`python -m custom_components.ocpp16.core`, see `__main__.py`), and even ships an interactive
   console (`console.py`) for that standalone mode. This is a project-wide invariant, not a
   preference — see `AGENTS.md`.
2. **Everything else under `custom_components/ocpp16/`** — the Home Assistant integration layer that
   wires `core/` into HA's config entries, device/entity registries, and services.

Nothing in `core/` may import from the HA layer, and the HA layer never reaches into `core/`'s
private state — only through the three objects `core/app.py`'s `CentralSystemApp` exposes:
`registry`, `query_service`, and `command_service` (plus `events` for the coordinator).

## Directory Structure

```text
custom_components/ocpp16/
├── __init__.py              # Entry setup/unload/migration, device registration
├── config_flow.py           # Thin discovery shim — re-exports Ocpp16ConfigFlow
├── const.py                 # Domain, config keys, the capability bitmask, status mapping
├── runtime.py                # Ocpp16EntryData / Ocpp16ConfigEntry (entry.runtime_data shape)
├── services.yaml             # Service schemas (legacy filename, AGENTS.md keeps it)
├── translations/en.json
├── core/                     # Standalone OCPP 1.6 Central System — zero homeassistant.* imports
│   ├── app.py                 # CentralSystemApp: composition root
│   ├── config.py, transport.py, logging_setup.py, console.py, __main__.py
│   ├── domain/                 # registry, connector_state, transactions, meter_values, events,
│   │                            # commands (CommandService), query (QueryServiceImpl), models
│   └── ocpp16/                 # OCPP 1.6 message handlers, python-ocpp glue, watchdog
├── coordinator/               # Thin push coordinator — see "Push, not poll" below
├── config_flow_handler/       # The real config flow (config_flow.py, options_flow.py)
├── entity/                    # Ocpp16ConnectorEntity/Ocpp16ChargePointEntity — shared entity bases
├── entity_utils/              # Device-info helpers (device.py): charge-point/connector DeviceInfo
├── sensor/                    # charge_point_state, current_power, effective_power_limit, measurand, ...
├── switch/                    # start_stop, availability
├── number/                    # power_limit
├── button/                    # reset, unlock_connector
├── service_actions/           # The 9 HA services — see docs/development/INTEROP_CONTRACT.md
└── utils/                     # interop.py: the REQ-0035 capability adapter
```

Every `<platform>/` and `service_actions/` package follows the same shape: `__init__.py` holds
`async_setup_entry`/registration plus anything two or more siblings would otherwise duplicate
(`_SensorManager`, `_SERVICES`), and a private `_base.py`/`_resolvers.py` holds what siblings
import from each other — never from `__init__.py` itself, which would create a circular import
since `__init__.py` imports the concrete entity/handler classes _from_ those siblings.

## Push, not poll

`iot_class: local_push` is not just a manifest field here — OCPP has no polling loop at all.

```text
Charge Point ──WebSocket──▶ core/ocpp16 handlers ──▶ core/domain stores (registry, connector_state,
                                                       transactions, meter_values)
                                                              │
                                                              ▼
                                                     EventBus.publish(StateChangeEvent)
                                                              │
                              ┌───────────────────────────────┼───────────────────────────┐
                              ▼                                ▼                           ▼
                   __init__.py's device-             Ocpp16Coordinator                (any other direct
                   registration listener        (async_set_updated_data)             query_service.subscribe()
                              │                                │                       caller)
                              ▼                                ▼
                   device_registry.async_get_or_create   coordinator's own listeners fire synchronously:
                                                          _SensorManager/_SwitchManager (create new
                                                          entities) and every existing entity's
                                                          _handle_coordinator_update (re-render)
```

`EventBus.publish()` calls its listeners in subscription order, and
`DataUpdateCoordinator.async_set_updated_data()` triggers the coordinator's own listeners
**synchronously, inside that same call** — so the device-registration listener must subscribe
_before_ the coordinator is constructed, or a connector device's `via_device` can point at a
charge-point device that does not exist yet on the very first event. `__init__.py` orders this
deliberately; see `DECISIONS.md`.

### The coordinator is deliberately thin

`Ocpp16Coordinator(DataUpdateCoordinator[StateChangeEvent | None])` holds only the _last_ event, not
a materialized snapshot — `update_interval=None`, no polling. Entities do **not** read
`coordinator.data` for their values; they read `QueryService`/`CommandService` directly in their
property getters (a free, always-current in-memory read, no I/O), and only use the coordinator for
lifecycle/`available` plumbing and to know _when_ to re-render or check whether a new
charge point/connector/measurand appeared. `coordinator.data` exists solely so a listener can
filter by relevance (e.g. `Ocpp16EffectivePowerLimitSensor` ignoring events for a different
connector) before doing anything expensive. See `DECISIONS.md` for why this reading of "entities
read the coordinator, never reach past it" was chosen over materializing a second data copy.

## Core Components

### `core/` — the standalone Central System

**Key classes:** `CentralSystemApp` (composition root), `QueryServiceImpl` (read-only facade over
the domain stores), `CommandService` (Central-System-initiated OCPP calls: RemoteStart/Stop, Reset,
UnlockConnector, Get/ChangeConfiguration, Set/ClearChargingProfile, GetCompositeSchedule,
ChangeAvailability), `ChargePointRegistryStore`, `ConnectorStateStore`, `TransactionManager`,
`MeterValueStore`, `EventBus`.

### `coordinator/`

**Key class:** `Ocpp16Coordinator` (exported from `coordinator/__init__.py`). See "Push, not poll"
above — this is not the usual polling `DataUpdateCoordinator`.

### `config_flow_handler/`

Single-step `user` flow: host/port for the WebSocket listen address land in `entry.data`
(connection-critical, per config-flow convention); the optional authorization file path and
default idTag land in `entry.options` (changeable afterwards without recreating the entry).
`unique_id` is a random UUID — host/port are never a valid unique ID source (`AGENTS.md`) — so a
duplicate host:port is caught explicitly via `_host_port_already_configured()` instead of the usual
`_abort_if_unique_id_configured()`.

**Key classes:** `Ocpp16ConfigFlow`, `Ocpp16OptionsFlow`.

### `entity/` + `entity_utils/`

**Key classes:** `Ocpp16ConnectorEntity` and `Ocpp16ChargePointEntity` (in `entity/base.py`) — the
shared bases every connector-scoped and charge-point-scoped entity extends respectively: unique ID
(`{entry_id}:{len(charge_point_id)}:{charge_point_id}:{connector_id}_{entity_key}` for connector
entities — the length-prefixed `charge_point_id` makes the split unambiguous regardless of its
content, see [`INTEROP_CONTRACT.md`](./INTEROP_CONTRACT.md) for the full addressing scheme), device
info via `entity_utils/device.py`, and the `available` override (online-status check, not
`last_update_success` — the coordinator never fails in a way that would make that meaningful).

## Platform Organization

Each platform (`sensor/`, `switch/`, `number/`, `button/`) follows this pattern:

```text
<platform>/
├── __init__.py               # async_setup_entry, the _<Platform>Manager that creates entities
│                              # dynamically as connectors/measurands are discovered, PARALLEL_UPDATES
├── _base.py                  # The platform's _Ocpp...Base(Ocpp16Connector|ChargePointEntity, <PlatformEntity>)
└── <entity_name>.py           # One entity class per file (AGENTS.md), imports the base from ._base
```

There is no `EntityDescription`/`value_fn` pattern here — each entity class has genuinely distinct
read/write logic (a status sensor, a measurand sensor, a power-limit sensor that makes its own
OCPP call), not a parameterized copy of its siblings.

## Service Actions

**Directory:** `service_actions/`

The 7 HA services OCPP exposes are **the interface a separate load-management integration is meant
to consume** — see [`INTEROP_CONTRACT.md`](./INTEROP_CONTRACT.md) for the full capability table,
addressing scheme, and stability rules. Registered once in `async_setup()` (not
`async_setup_entry()`, per the Quality Scale `action-setup` rule), independent of how many config
entries exist.

## AI Agent Context

Agent-facing content is layered so each piece is loaded only when it is relevant:

| Layer                             | Loaded                      | Contains                                          |
| --------------------------------- | --------------------------- | ------------------------------------------------- |
| `AGENTS.md`                       | always                      | project identity, workflow rules, validation loop |
| `.agents/instructions/*.md`       | per touched file            | passive style rules for one file type             |
| `.agents/skills/*/SKILL.md`       | when a task matches         | active procedures for a specific kind of work     |
| `docs/development/`, `docs/user/` | when a human or agent reads | explanations, decisions, guides — this document   |

Style rules belong in `.agents/instructions/`, procedures belong in a skill, explanations belong in `docs/`.

One copy of each instruction file serves two agents: GitHub Copilot and VS Code match its `applyTo` glob string,
Claude Code matches the same patterns via `paths` (a YAML list, one pattern per item) and reaches the same files
through the `.claude/rules/instructions` symlink. Codex has no comparable file-triggered mechanism — its nested
`AGENTS.md` support keys off the working directory rather than the file being edited — so it relies on the root
`AGENTS.md` plus the pointers each skill carries.

The skill catalogue, the symlink layout that makes one directory work for every agent vendor, and the rules for writing
a new skill are documented in [`.agents/skills/README.md`](../../.agents/skills/README.md).

For working with AI coding agents in this repository, see [`AI_AGENTS.md`](./AI_AGENTS.md).

## Key Design Decisions

See [DECISIONS.md](./DECISIONS.md) for architectural and design decisions made during development,
and [INTEROP_CONTRACT.md](./INTEROP_CONTRACT.md) specifically for the load-management interface.

## Extension Points

### Adding a New Platform

1. Create `custom_components/ocpp16/<platform>/` with `__init__.py`, `_base.py`, and one file per
   entity class.
2. Add `Platform.<NAME>` to `PLATFORMS` in `const.py` (alphabetical).
3. Follow the `sensor/`/`switch/` pattern for the manager class and coordinator subscription.

### Adding a New Service Action

1. Create the handler module in `service_actions/<name>.py`, using `service_actions/_resolvers.py`
   for device/entry lookups.
2. Add the service to `services.yaml` (legacy filename) with its schema.
3. Add the `(SERVICE_NAME, SCHEMA, handler)` tuple to `_SERVICES` in `service_actions/__init__.py`.
4. If it changes what a load-management integration could observe or control, update
   [`INTEROP_CONTRACT.md`](./INTEROP_CONTRACT.md).

### Modifying the Domain Model

Domain types (`ChargePointSnapshot`, `ConnectorSnapshot`, `MeterSample`, ...) live in
`core/domain/models.py` and are shared with OCPP's own standalone console — treat a field
rename/removal there as a breaking change to `core/`, independent of anything in the HA layer.

## Testing Strategy

- **`tests/` mirrors `custom_components/ocpp16/`** for the HA layer (`test_config_flow.py`,
  `test_coordinator.py`, `sensor/`, `switch/`, `test_service_actions.py`).
- There is no HTTP API client to mock — `tests/conftest.py`'s fixture factories
  (`boot_charge_point`, `record_meter_sample`, `publish_state_change`) seed `CentralSystemApp`'s
  real domain stores the same way an OCPP-1.6 handler would, and `mock_charge_point_connection`
  is an `AsyncMock` satisfying `core/domain/connection.py`'s `ChargePointConnection` protocol.
- `core/`'s own test suite (~210 tests) lives in the separate OCPP source repository and is not
  yet part of this one.

## Dependencies

Core dependencies (see `manifest.json`):

- `ocpp` — OCPP 1.6 message (de)serialization
- `websockets` — the WebSocket server `core/transport.py` runs
- `prompt_toolkit` — the standalone console (`core/console.py`), never imported by the HA layer

Development dependencies (see `requirements_dev.txt`, `requirements_test.txt`).
