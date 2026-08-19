# Examples

This page provides ready-to-use examples for automations, dashboards, and blueprints
with the OCCP - OCPP 1.6 Central System custom integration.

Replace entity/device IDs like `sensor.ladepunkt_1` and `<connector device id>` with your actual
ones after setting up the integration — see [GETTING_STARTED.md](./GETTING_STARTED.md) for how
devices/entities are named.

## Automations

### Notify when a connector faults

```yaml
automation:
  - alias: "Alert on connector fault"
    trigger:
      - trigger: state
        entity_id: sensor.ladepunkt_1
        to: "error"
    action:
      - action: notify.notify
        data:
          title: "Charge point fault"
          message: >-
            {{ state_attr(trigger.entity_id, 'friendly_name') }}:
            {{ state_attr(trigger.entity_id, 'error_code') }}
```

### Turn off a load when charging starts

```yaml
automation:
  - alias: "Pause dishwasher while charging"
    trigger:
      - trigger: state
        entity_id: sensor.ladepunkt_1
        to: "charging"
    action:
      - action: switch.turn_off
        target:
          entity_id: switch.dishwasher
```

### Limit charging power on a schedule

```yaml
automation:
  - alias: "Reduce charging power overnight"
    trigger:
      - trigger: time
        at: "22:00:00"
    action:
      - action: occp.set_power_limit
        data:
          device_id: <connector device id>
          limit_w: 3700

  - alias: "Restore charging power in the morning"
    trigger:
      - trigger: time
        at: "06:00:00"
    action:
      - action: occp.clear_power_limit
        data:
          device_id: <connector device id>
```

This is the pattern a dedicated load-management integration would automate dynamically instead of
on a fixed schedule — see [INTEROP_CONTRACT.md](../development/INTEROP_CONTRACT.md) if you're
building one.

### Start a transaction remotely

```yaml
automation:
  - alias: "Start charging when I arrive home"
    trigger:
      - trigger: zone
        entity_id: person.me
        zone: zone.home
        event: enter
    condition:
      - condition: state
        entity_id: sensor.ladepunkt_1
        state: "not_connected"
        # only fires once a cable is actually plugged in, via the "ready" state below --
        # adjust to your own workflow
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.ladepunkt_1
```

### Use a blueprint for connector-error alerts

Save this as a blueprint file and import it in Home Assistant:

```yaml
blueprint:
  name: OCCP Connector Error Alert
  description: Send a notification when a connector's state becomes "error".
  domain: automation
  input:
    state_entity:
      name: Charge Point State sensor
      selector:
        entity:
          domain: sensor
          integration: occp
    notify_target:
      name: Notification service
      default: notify.notify
      selector:
        text:

trigger:
  - trigger: state
    entity_id: !input state_entity
    to: "error"

action:
  - action: !input notify_target
    data:
      message: >-
        {{ state_attr(trigger.entity_id, 'friendly_name') }} reported an error:
        {{ state_attr(trigger.entity_id, 'error_code') }}
```

## Dashboard Cards

### Connector status card

```yaml
type: entities
title: Ladepunkt 1
entities:
  - entity: sensor.ladepunkt_1
    name: State
  - entity: sensor.ladepunkt_1_power
    name: Current Power
  - entity: switch.ladepunkt_1
    name: Charging
  - entity: switch.ladepunkt_1_2
    name: Available
```

### Power graph

```yaml
type: sensor
entity: sensor.ladepunkt_1_power
name: Charging Power
graph: line
```

### Multi-connector glance

```yaml
type: glance
title: Charge Points
entities:
  - entity: sensor.ladepunkt_1
    name: Connector 1
  - entity: sensor.ladepunkt_2
    name: Connector 2
show_state: true
```

### Energy history

```yaml
type: history-graph
title: Energy Delivered (last 24 h)
entities:
  - entity: sensor.ladepunkt_1_energy_active_import_register
hours_to_show: 24
```

The exact entity ID for the energy measurand depends on which `Energy.*` measurand your charge
point actually reports — check **Settings** → **Devices & Services** → **Entities** after your
first transaction.

## Related Documentation

- [Configuration Reference](./CONFIGURATION.md) - All configuration options and the full service reference
- [Getting Started](./GETTING_STARTED.md) - Installation and initial setup
- [Interop Contract](../development/INTEROP_CONTRACT.md) - Building another integration against OCCP
- [GitHub Issues](https://github.com/toolsfactory/occp-ha/issues) - Report problems
