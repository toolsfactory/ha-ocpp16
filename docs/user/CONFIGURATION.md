# Configuration Reference

This document describes all configuration options and settings available in the OCPP 1.6 Central System custom integration.

## Integration Configuration

### Initial Setup Options

These options are configured during initial setup via the Home Assistant UI.

| Option                 | Type    | Required | Default   | Description                                                                                       |
| ---------------------- | ------- | -------- | --------- | ------------------------------------------------------------------------------------------------- |
| **Host**               | string  | Yes      | `0.0.0.0` | Bind address the OCPP WebSocket server listens on                                                 |
| **Port**               | integer | Yes      | `9000`    | Listen port for the OCPP WebSocket server                                                         |
| **Certificate Path**   | string  | No       | —         | Path to a PEM TLS certificate (see below); set together with Private Key Path for direct `wss://` |
| **Private Key Path**   | string  | No       | —         | Path to the PEM private key matching the certificate                                              |
| **Authorization File** | string  | No       | —         | Path to a JSON idTag allow-list (see below); empty = reject every idTag                           |
| **Default idTag**      | string  | No       | —         | idTag the `start_stop` switch uses for remote-start                                               |
| **Max Power Limit**    | number  | No       | `22000`   | Upper bound (watts) for the `number.power_limit_w` entity                                         |

Host and port are test-bound during setup — a port already in use is rejected immediately with a
clear error instead of failing later. Certificate Path and Private Key Path are validated the same
way: an unreadable file or an invalid/mismatched pair is a form error, not a later setup failure.

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
`expiryDate` (ISO 8601) rejects it once past.

**Leaving the authorization file unset does not accept every idTag — it rejects every idTag.**
With no file configured, OCPP's authorization provider has an empty allow-list, so
`authorize_id_token` and every `RemoteStartTransaction`/`StartTransaction` idTag check comes back
`Invalid` (`core/domain/authorization.py`'s `StaticAuthorizationProvider.authorize()` returns
`Invalid` for any tag not found in its entries — an empty provider has none). Set an authorization
file listing at least the `Default idTag` if you want the `start_stop` switch or
`ocpp16.authorize_id_token` to work at all.

### TLS Certificate (`wss://`)

Setting both **Certificate Path** and **Private Key Path** makes the OCPP WebSocket server accept
`wss://` connections directly, using Python's built-in `ssl` module — no reverse proxy needed. This
is deliberate: unlike Home Assistant's own web UI, which a reverse proxy fronts via ordinary
HTTP-vhost `proxy_pass`, OCPP charge points connect straight to `IP:port` and are not HTTP clients
that understand host-based routing. Terminating TLS for OCPP through a reverse proxy needs
TCP-stream proxying (e.g. nginx's `stream {}` block) — a materially harder setup for most home
users than pointing this integration at a certificate and key file.

Both files must be PEM-encoded, and the key must match the certificate — an invalid or mismatched
pair is rejected at setup/reconfigure time with a form error, the same way an unreadable
authorization file is. Leave both fields empty to keep plain `ws://`, which stays the default.

```bash
# Example: a self-signed certificate for local testing (a real deployment should use a
# certificate a charge point will actually trust, e.g. from your own internal CA).
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:prime256v1 -nodes \
  -keyout key.pem -out cert.pem -days 365 -subj "/CN=homeassistant.local"
```

### Options Flow

The **Authorization File**, **Default idTag**, and **Max Power Limit** can all be changed after
setup, without recreating the integration — the entry reloads automatically to apply the change:

1. Go to **Settings** → **Devices & Services**
2. Find "OCPP 1.6 Central System"
3. Click **Configure**
4. Modify the authorization file path, default idTag, or max power limit
5. Click **Submit**

Setting a **Default idTag** requires an authorization file that actually accepts it — an unknown,
blocked, or expired idTag is rejected at this step rather than saved and failing later.

Changing **Max Power Limit** updates every connector's `number.power_limit_w` entity's maximum
value immediately — it does not itself change any charge point's actual power limit, only what the
number entity will let you set.

### Reconfigure Flow (Host/Port/TLS)

The **Host**, **Port**, **Certificate Path**, and **Private Key Path** can also be changed after
setup, without deleting and re-adding the entry (and losing its devices/entities/history) — they
are connection-critical settings, grouped together the same way Host/Port already were:

1. Go to **Settings** → **Devices & Services**
2. Find the specific "OCPP (host:port)" entry you want to change
3. Open its menu (⋮) and select **Reconfigure**
4. Enter the new host/port, and optionally add or remove a certificate/key pair — the same
   port-in-use and TLS-pair checks from initial setup apply
5. Click **Submit** — the entry reloads on the new address automatically

The Authorization File and Default idTag are not part of this flow — change those via **Configure**
(the options flow above) instead.

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

The integration provides 9 services. `device_id` fields expect the connector or charge-point
device (as noted per service) — resolve it via **Settings** → **Devices & Services** → the device,
or the device selector Home Assistant's service UI offers for these fields automatically. See
[INTEROP_CONTRACT.md](../development/INTEROP_CONTRACT.md) for the full machine-readable contract
if you're building another integration against these.

### `ocpp16.set_power_limit`

Set a connector's charging power limit.

| Field       | Required | Description                |
| ----------- | -------- | -------------------------- |
| `device_id` | Yes      | Connector device           |
| `limit_w`   | Yes      | Power limit in watts (> 0) |
| `phases`    | No       | Number of phases (1–3)     |

```yaml
action: ocpp16.set_power_limit
data:
  device_id: <connector device id>
  limit_w: 7400
  phases: 3
```

### `ocpp16.clear_power_limit`

Remove a connector's charging power limit.

```yaml
action: ocpp16.clear_power_limit
data:
  device_id: <connector device id>
```

### `ocpp16.authorize_id_token`

Check whether an idTag is authorized, without starting a transaction.

```yaml
action: ocpp16.authorize_id_token
data:
  charge_point_id: CP001
  id_token: TAG001
```

`charge_point_id` alone is ambiguous the moment two loaded OCPP instances happen to see the same
OCPP `chargePointId` — the call is answered by whichever instance's registry is scanned first,
which is not guaranteed to be the one you meant. Add `device_id` (the charge point's or a
connector's device) to resolve it unambiguously instead:

```yaml
action: ocpp16.authorize_id_token
data:
  charge_point_id: CP001
  id_token: TAG001
  device_id: <charge point or connector device id>
```

If you only ever run a single OCPP instance, or are certain no two instances share a
`chargePointId`, omitting `device_id` is fine — it exists specifically for the multi-instance case.

### `ocpp16.reset`

Soft- or hard-reset the charge point.

```yaml
action: ocpp16.reset
data:
  device_id: <charge point device id>
  reset_type: Soft
```

### `ocpp16.unlock_connector`

Ask the charge point to unlock a connector.

```yaml
action: ocpp16.unlock_connector
data:
  device_id: <connector device id>
```

### `ocpp16.get_configuration`

Read one or more OCPP configuration keys (all of them if `keys` is omitted).

```yaml
action: ocpp16.get_configuration
data:
  device_id: <charge point device id>
  keys: [HeartbeatInterval]
```

### `ocpp16.change_configuration`

Set a single OCPP configuration key.

```yaml
action: ocpp16.change_configuration
data:
  device_id: <charge point device id>
  key: HeartbeatInterval
  value: "300"
```

### `ocpp16.trigger_message`

Ask the charge point to resend a specific OCPP message (`BootNotification`,
`DiagnosticsStatusNotification`, `FirmwareStatusNotification`, `Heartbeat`, `MeterValues`, or
`StatusNotification`). Unlike the services above, a non-`Accepted` status is returned as response
data rather than raised as an error — it doesn't change any charge-point state, so it's informative
rather than a failure.

```yaml
action: ocpp16.trigger_message
data:
  device_id: <charge point device id>
  requested_message: StatusNotification
```

### `ocpp16.get_diagnostics`

Ask the charge point to upload a diagnostics file to a location you provide (an FTP or HTTP(S)
server you operate). OCPP 1.6 defines no accept/reject status for this call, so a successful call
always returns `{"file_name": ...}` (`file_name` may be `null` -- the charge point does not have to
know it yet).

```yaml
action: ocpp16.get_diagnostics
data:
  device_id: <charge point device id>
  location: ftp://ops.example.com/diagnostics/
  retries: 3
  retry_interval: 30
```

### Using Services in Automations

```yaml
automation:
  - alias: "Limit power overnight"
    trigger:
      - trigger: time
        at: "22:00:00"
    action:
      - action: ocpp16.set_power_limit
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
3. Search for "OCPP 1.6 Central System"
4. Configure with a different host/port

Each instance's devices/entities are entirely independent.

### Network Configuration

Charge points connect _to_ Home Assistant, not the other way around:

- Ensure the configured port is reachable from the charge point (open the port on Home Assistant's
  host firewall, forward it if the charge point is on a different network)
- The charge point must be configured with `ws://<home-assistant-host>:<port>/<chargePointId>` and
  subprotocol `ocpp1.6` — or `wss://` if you configured a Certificate/Private Key Path (see
  [TLS Certificate](#tls-certificate-wss) above); no reverse proxy is needed either way

### Push Behavior

OCPP does **not** poll — `iot_class: local_push`. Entities update the moment a charge point sends
a relevant OCPP message (`StatusNotification`, `MeterValues`, ...); there is no update interval to
configure and nothing to tune for responsiveness.

## Diagnostic Data

**Settings** → **Devices & Services** → **OCPP 1.6 Central System** → the three-dot menu →
**Download Diagnostics** exports a summary of what OCPP currently knows about the config entry and
each connected charge point: entry configuration, per-charge-point connection status and reconnect
count, vendor/model/firmware, and per-connector status, error code, and most recent transaction
(transaction ID, start/stop time, stop reason). Host, the authorization file path, the default
idTag, and a transaction's idTag are redacted; `charge_point_id` is deliberately not (it is already
visible everywhere in the UI as the device name — see
[DECISIONS.md](../development/DECISIONS.md#accepted-risk-charge_point_id-is-not-redacted-in-diagnostics)).
This is a point-in-time summary, not a full OCPP frame log — use debug logging (see
[GETTING_STARTED.md](./GETTING_STARTED.md#debug-logging)) for detailed protocol-level
troubleshooting.

## Blueprints

The integration works with Home Assistant Blueprints for reusable automations:

### Example Blueprint — Connector Error Alert

```yaml
blueprint:
  name: OCPP Connector Error Alert
  description: Notify when a connector's state becomes "error".
  domain: automation
  input:
    state_entity:
      name: Charge Point State sensor
      selector:
        entity:
          domain: sensor
          integration: ocpp16
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
- [PV-Surplus Charging](./PV_SURPLUS_CHARGING.md) - Complete example: charging from PV surplus with an EDL21 grid meter
- [Supported Devices](./SUPPORTED_DEVICES.md) - Real-hardware compatibility results (currently empty — no device validated yet)
- [Interop Contract](../development/INTEROP_CONTRACT.md) - Building another integration against OCPP
- [GitHub Issues](https://github.com/toolsfactory/ha-ocpp16/issues) - Report problems
