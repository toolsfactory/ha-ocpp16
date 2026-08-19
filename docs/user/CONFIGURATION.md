# Configuration Reference

This document describes all configuration options and settings available in the OCCP - OCPP 1.6 Central System custom integration.

## Integration Configuration

### Initial Setup Options

These options are configured during initial setup via the Home Assistant UI.

| Option                 | Type    | Required | Default   | Description                                                     |
| ---------------------- | ------- | -------- | --------- | --------------------------------------------------------------- |
| **Host**               | string  | Yes      | `0.0.0.0` | Bind address the OCPP WebSocket server listens on               |
| **Port**               | integer | Yes      | `9000`    | Listen port for the OCPP WebSocket server                       |
| **Authorization File** | string  | No       | —         | Path to a JSON idTag allow-list (see below); empty = accept all |
| **Default idTag**      | string  | No       | —         | idTag the `start_stop` switch uses for remote-start             |

Host and port are test-bound during setup — a port already in use is rejected immediately with a
clear error instead of failing later.

### Authorization File Format

```json
{
  "idTags": {
    "ABC123": { "blocked": false, "parentIdTag": null, "expiryDate": null },
    "DEF456": { "blocked": true }
  }
}
```

Every field except the key itself is optional. `blocked: true` rejects the tag outright;
`expiryDate` (ISO 8601) rejects it once past. Leave the authorization file unset to accept every
idTag without checking.

### Options Flow (Reconfiguration)

The **Authorization File** and **Default idTag** can be changed after setup, without recreating
the integration — the entry reloads automatically to apply the change:

1. Go to **Settings** → **Devices & Services**
2. Find "OCCP - OCPP 1.6 Central System"
3. Click **Configure**
4. Modify the authorization file path or default idTag
5. Click **Submit**

**Host and port cannot be changed this way** — they are fixed once the entry is created. To listen
on a different address/port, add a new config entry (see "Multiple Instances" below) and remove
the old one.

## Entity Configuration

### Entity Customization

Customize entities via the UI or `configuration.yaml`:

#### Via Home Assistant UI

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find and click the entity
3. Click the settings icon
4. Modify:
   - Entity ID
   - Name
   - Icon
   - Area assignment

#### Via configuration.yaml

```yaml
homeassistant:
  customize:
    sensor.ladepunkt_1_power:
      friendly_name: "Wallbox Power"
```

### Disabling Entities

If you don't need certain entities (e.g. a rarely-reported measurand sensor):

1. Go to **Settings** → **Devices & Services** → **Entities**
2. Find the entity
3. Click it, then click the **Settings** icon
4. Toggle **Enable entity** off

Disabled entities won't update or consume resources.

## Services

The integration provides 7 services. `device_id` fields expect the connector or charge-point
device (as noted per service) — resolve it via **Settings** → **Devices & Services** → the device,
or the device selector Home Assistant's service UI offers for these fields automatically. See
[INTEROP_CONTRACT.md](../development/INTEROP_CONTRACT.md) for the full machine-readable contract
if you're building another integration against these.

### `occp.set_power_limit`

Set a connector's charging power limit.

| Field       | Required | Description                |
| ----------- | -------- | -------------------------- |
| `device_id` | Yes      | Connector device           |
| `limit_w`   | Yes      | Power limit in watts (> 0) |
| `phases`    | No       | Number of phases (1–3)     |

```yaml
action: occp.set_power_limit
data:
  device_id: <connector device id>
  limit_w: 7400
  phases: 3
```

### `occp.clear_power_limit`

Remove a connector's charging power limit.

```yaml
action: occp.clear_power_limit
data:
  device_id: <connector device id>
```

### `occp.authorize_id_token`

Check whether an idTag is authorized, without starting a transaction.

```yaml
action: occp.authorize_id_token
data:
  charge_point_id: CP001
  id_token: TAG001
```

### `occp.reset`

Soft- or hard-reset the charge point.

```yaml
action: occp.reset
data:
  device_id: <charge point device id>
  reset_type: Soft
```

### `occp.unlock_connector`

Ask the charge point to unlock a connector.

```yaml
action: occp.unlock_connector
data:
  device_id: <connector device id>
```

### `occp.get_configuration`

Read one or more OCPP configuration keys (all of them if `keys` is omitted).

```yaml
action: occp.get_configuration
data:
  device_id: <charge point device id>
  keys: [HeartbeatInterval]
```

### `occp.change_configuration`

Set a single OCPP configuration key.

```yaml
action: occp.change_configuration
data:
  device_id: <charge point device id>
  key: HeartbeatInterval
  value: "300"
```

### Using Services in Automations

```yaml
automation:
  - alias: "Limit power overnight"
    trigger:
      - trigger: time
        at: "22:00:00"
    action:
      - action: occp.set_power_limit
        data:
          device_id: <connector device id>
          limit_w: 3700
```

## Advanced Configuration

### Multiple Instances

You can add multiple config entries, each running its own independent WebSocket server on a
different port — useful for one listen port per site, or to separate charge points by network
segment:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "OCCP - OCPP 1.6 Central System"
4. Configure with a different host/port

Each instance's devices/entities are entirely independent.

### Network Configuration

Charge points connect _to_ Home Assistant, not the other way around:

- Ensure the configured port is reachable from the charge point (open the port on Home Assistant's
  host firewall, forward it if the charge point is on a different network)
- The charge point must be configured with `ws://<home-assistant-host>:<port>/<chargePointId>` and
  subprotocol `ocpp1.6` — OCCP does not support `wss://` directly (put a reverse proxy in front if
  the charge point requires TLS)

### Push Behavior

OCCP does **not** poll — `iot_class: local_push`. Entities update the moment a charge point sends
a relevant OCPP message (`StatusNotification`, `MeterValues`, ...); there is no update interval to
configure and nothing to tune for responsiveness.

## Diagnostic Data

Not yet implemented — this integration does not currently provide a "Download Diagnostics" export.
Use debug logging (see [GETTING_STARTED.md](./GETTING_STARTED.md#debug-logging)) for
troubleshooting in the meantime.

## Blueprints

The integration works with Home Assistant Blueprints for reusable automations:

### Example Blueprint — Connector Error Alert

```yaml
blueprint:
  name: OCCP Connector Error Alert
  description: Notify when a connector's state becomes "error".
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

## Configuration Examples

See [EXAMPLES.md](./EXAMPLES.md) for complete automation and dashboard examples.

## Troubleshooting Configuration

### Config Entry Fails to Load

If the integration fails to load after configuration:

1. Check Home Assistant logs for errors
2. Confirm the configured port isn't already in use by something else
3. Verify the authorization file path (if set) is readable by Home Assistant
4. Try removing and re-adding the integration

### Options Don't Save

If configuration changes aren't persisted:

1. Check for validation errors in the UI
2. Review logs for detailed error messages
3. Try restarting Home Assistant

## Related Documentation

- [Getting Started](./GETTING_STARTED.md) - Installation and initial setup
- [Examples](./EXAMPLES.md) - Automation and dashboard examples
- [Interop Contract](../development/INTEROP_CONTRACT.md) - Building another integration against OCCP
- [GitHub Issues](https://github.com/toolsfactory/occp-ha/issues) - Report problems
