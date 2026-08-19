# Getting Started with OCCP - OCPP 1.6 Central System

This guide will help you install and set up the OCCP - OCPP 1.6 Central System custom integration for Home Assistant.

OCCP turns Home Assistant into an OCPP 1.6 **Central System**: it runs its own WebSocket server
that charge points connect _to_. There is no external cloud service or device IP to poll — Home
Assistant is the server, and charge points are the clients.

## Prerequisites

- Home Assistant 2025.7.0 or newer
- HACS (Home Assistant Community Store) installed
- An OCPP 1.6 charge point (or a simulator, e.g.
  [shiv3/ocpp-cp-simulator](https://github.com/shiv3/ocpp-cp-simulator)) that can be pointed at a
  custom OCPP backend URL, and network connectivity from that charge point to Home Assistant
- A free port on the Home Assistant host for OCCP's WebSocket server (default `9000`)

## Installation

### Via HACS (Recommended)

1. Open HACS in your Home Assistant instance
2. Go to "Integrations"
3. Click the three dots in the top right corner
4. Select "Custom repositories"
5. Add this repository URL: `https://github.com/toolsfactory/occp-ha`
6. Set category to "Integration"
7. Click "Add"
8. Find "OCCP - OCPP 1.6 Central System" in the integration list
9. Click "Download"
10. Restart Home Assistant

### Manual Installation

1. Download the latest release from the [releases page](https://github.com/toolsfactory/occp-ha/releases)
2. Extract the `occp` folder from the archive
3. Copy it to `custom_components/occp/` in your Home Assistant configuration directory
4. Restart Home Assistant

## Initial Setup

After installation, add the integration:

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "OCCP - OCPP 1.6 Central System"
4. Follow the configuration steps:

### Step 1: Listen Address

Enter where OCCP's WebSocket server should listen for charge point connections:

- **Host:** The bind address (default `0.0.0.0` — every network interface)
- **Port:** The listen port (default `9000`)

Home Assistant test-binds this address/port before creating the entry, so a port already in use by
something else is rejected immediately with a clear error rather than failing later.

### Step 2: Optional Settings

- **Authorization File:** Path to a JSON file with a static idTag allow-list (see
  [CONFIGURATION.md](./CONFIGURATION.md) for the format). **Leaving this empty rejects every
  idTag**, not the other way around — set it (listing at least your **Default idTag**, below) if
  you want to remote-start a transaction or use `occp.authorize_id_token` at all.
- **Default idTag:** The idTag OCCP uses when the `start_stop` switch remote-starts a transaction.
  Required only if you plan to use that switch — and must appear in the authorization file above,
  or the charge point will reject the transaction as unauthorized.

Both of these can be changed later without recreating the integration — see
[CONFIGURATION.md](./CONFIGURATION.md).

Click **Submit** to complete setup. Home Assistant now starts listening for charge point
connections immediately.

### Step 3: Point Your Charge Point at Home Assistant

Configure your charge point's (or simulator's) OCPP backend URL to:

```text
ws://<home-assistant-host>:<port>/<chargePointId>
```

using WebSocket subprotocol `ocpp1.6`. `<chargePointId>` is whatever identity the charge point
sends — OCCP does not require pre-registration.

## What Gets Created

Devices and entities appear **automatically** the moment a charge point connects and sends its
first `BootNotification` — there is nothing to register manually.

### Devices

- **One device per charge point**, named "Ladestation `<chargePointId>`" — manufacturer, model,
  and firmware version come from the `BootNotification`.
- **One sub-device per connector** (`via_device` pointing at the charge point), named
  "Ladepunkt `<connectorId>`". `connectorId 0` (the charge point as a whole, per OCPP 1.6) never
  gets its own device or entities.

### Entities (per connector)

#### Sensors

- **Charge Point State** — five-value connector state (`not_connected`/`ready`/`charging`/
  `unavailable`/`error`), with the raw OCPP status and error code as attributes
- **Current Power** — the connector's current charging power in watts
- **Effective Power Limit** — the power limit currently in effect, read back from the charge point
- **Active Phases** — how many phases currently show a positive current, with each phase's current
  as attributes
- **Measurand sensors** — one dynamic sensor per measurand the charge point actually reports
  (energy, voltage, current, temperature, state of charge, ...)

#### Switches

- **Start/Stop** — remote-starts or stops a transaction
- **Availability** — takes the connector operative or inoperative

See the [README](../../README.md#available-entities) for full details, and
[INTEROP_CONTRACT.md](../development/INTEROP_CONTRACT.md) if you're building another integration
against these entities and services.

## First Steps

### Dashboard Cards

Add entities to your dashboard:

1. Go to your dashboard
2. Click **Edit Dashboard** → **Add Card**
3. Choose card type (e.g., "Entities", "Glance")
4. Select entities from "OCCP - OCPP 1.6 Central System"

Example entities card:

```yaml
type: entities
title: Charge Point CP001
entities:
  - sensor.ladepunkt_1
  - sensor.ladepunkt_1_power
  - switch.ladepunkt_1
  - switch.ladepunkt_1_2
```

### Automations

**Example — notify when charging starts:**

```yaml
automation:
  - alias: "Notify when charging starts"
    trigger:
      - trigger: state
        entity_id: sensor.ladepunkt_1
        to: "charging"
    action:
      - action: notify.notify
        data:
          message: "Charging started on connector 1."
```

**Example — remote-start a transaction on a schedule:**

```yaml
automation:
  - alias: "Start charging at night"
    trigger:
      - trigger: time
        at: "22:00:00"
    action:
      - action: switch.turn_on
        target:
          entity_id: switch.ladepunkt_1
```

See [EXAMPLES.md](./EXAMPLES.md) for more, including the power-limiting services.

## Troubleshooting

### Charge point does not appear

1. Confirm the charge point's configured OCPP backend URL matches
   `ws://<host>:<port>/<chargePointId>` and uses subprotocol `ocpp1.6`
2. Check that nothing else on the network is already bound to the configured port
3. Check the Home Assistant log for connection attempts and rejected connections

### Entities show "Unknown" or "Unavailable"

- **Current Power** and **Effective Power Limit** show `unknown` until the charge point has
  actually reported a matching value — that is expected, not an error, if no transaction is
  running yet.
- `unavailable` means the charge point itself isn't connected. Check that its connection is still
  active (**Settings** → **Devices & Services** → the charge-point device) and review the log.

### Debug Logging

Enable debug logging to troubleshoot issues:

```yaml
logger:
  default: warning
  logs:
    custom_components.occp: debug
```

Add this to `configuration.yaml`, restart, and reproduce the issue. Check logs for detailed information.

## Next Steps

- See [CONFIGURATION.md](./CONFIGURATION.md) for detailed configuration options and the full service reference
- See [EXAMPLES.md](./EXAMPLES.md) for more automation examples
- Report issues at [GitHub Issues](https://github.com/toolsfactory/occp-ha/issues)

## Support

For help and discussion:

- [GitHub Discussions](https://github.com/toolsfactory/occp-ha/discussions)
- [Home Assistant Community Forum](https://community.home-assistant.io/)
