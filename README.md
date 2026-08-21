# OCPP 1.6 Central System

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

**✨ Develop in the cloud:** Want to contribute or customize this integration? Open it directly in GitHub Codespaces - no local setup required!

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/toolsfactory/ocpp-ha?quickstart=1)

## ✨ Features

OCPP turns Home Assistant into an OCPP 1.6 **Central System**: it runs its own WebSocket server that
charge points connect to, rather than polling a cloud API.

- **Easy Setup**: Configure the listen address/port through the UI - no YAML required
- **Push-Based**: Charge points and connectors are discovered automatically as they connect - nothing
  to pre-register
- **Live Status**: Five-value connector state (not connected / ready / charging / unavailable /
  error), plus the raw OCPP status and error code as attributes
- **Energy Monitoring**: Current charging power and every measurand a charge point reports
  (energy, voltage, current, temperature, state of charge, ...) as dynamic sensors
- **Remote Control**: Start and stop transactions, and take a connector operative/inoperative,
  directly from Home Assistant
- **Power Limiting**: Set or clear a charging power limit per connector, with the effective limit
  read back from the charge point
- **Static Authorization**: An optional JSON allow-list of idTags a charge point may accept for
  transactions
- **Custom Services**: Set/clear a connector's power limit and check an idTag's authorization status
  from automations

**This integration sets up the following platforms.**

| Platform | Description                                                                                |
| -------- | ------------------------------------------------------------------------------------------ |
| `sensor` | Connector state, current charging power, effective power limit, and per-measurand readings |
| `switch` | Start/stop a transaction, and toggle a connector operative/inoperative                     |

Each charge point becomes a Home Assistant device, with every connector as its own sub-device.

## 🚀 Quick Start

### Step 1: Install the Integration

**Prerequisites:** This integration requires [HACS](https://hacs.xyz/) (Home Assistant Community Store) to be installed.

Click the button below to open the integration directly in HACS:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=toolsfactory&repository=ocpp-ha&category=integration)

Then:

1. Click "Download" to install the integration
2. **Restart Home Assistant** (required after installation)

> [!NOTE]
> The My Home Assistant redirect will first take you to a landing page. Click the button there to open your Home Assistant instance.

<details>
<summary><strong>Manual Installation (Advanced)</strong></summary>

If you prefer not to use HACS:

1. Download the `custom_components/ocpp/` folder from this repository
2. Copy it to your Home Assistant's `custom_components/` directory
3. Restart Home Assistant

</details>

### Step 2: Add and Configure the Integration

**Important:** You must have installed the integration first (see Step 1) and restarted Home Assistant!

#### Option 1: One-Click Setup (Quick)

Click the button below to open the configuration dialog:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ocpp)

Follow the setup wizard:

1. Enter the address and port the OCPP WebSocket server should listen on (defaults to
   `0.0.0.0:9000` - reachable from every network interface)
2. Optionally point at a JSON file with a static idTag allow-list
3. Optionally set a default idTag to use when starting a transaction from the `start_stop` switch
4. Click Submit

Home Assistant now starts listening for charge point connections. Point your charge point's OCPP
backend URL at `ws://<this host>:<port>/<chargePointId>`.

#### Option 2: Manual Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **"+ Add Integration"**
3. Search for "OCPP 1.6 Central System"
4. Follow the same setup steps as Option 1

You can add more than one config entry (e.g. one listen port per site) - each runs its own
independent WebSocket server.

### Step 3: Connect a Charge Point

Devices and entities appear automatically the moment a charge point connects and sends its first
`BootNotification` - there is nothing to register manually. Find them in **Settings** → **Devices &
Services** → **OCPP 1.6 Central System**.

## Available Entities

Most entities are created per connector as soon as a charge point reports it (connector 0, the
charge point as a whole, never gets its own connector entities). A few are charge-point-wide
instead, noted below.

### Sensors

- **Charge Point State**: Five-value connector state (`not_connected`, `ready`, `charging`,
  `unavailable`, `error`), with the raw OCPP status, error code, and supported capabilities as
  attributes
- **Current Power**: The connector's current charging power in watts, from the
  `Power.Active.Import` measurand
- **Effective Power Limit**: The power limit currently in effect, read back from the charge point
  via `GetCompositeSchedule`
- **Active Phases**: How many phases currently have a positive `Current.Import` reading, with each
  phase's current (in amps) as attributes
- **Measurand sensors**: One dynamic sensor per measurand a charge point actually reports (energy,
  voltage, current, temperature, state of charge, ...), split by phase where the charge point
  reports one
- **Last Heartbeat** (charge-point-wide): Timestamp of the charge point's most recent OCPP
  `Heartbeat.req`
- **Transaction ID**: The connector's most recent transaction ID, active or already stopped
- **Session Duration**: How long the connector's most recent session has been (or was) running
- **Session Energy**: Energy delivered during the connector's most recent session, in Wh
- **Stop Reason**: The OCPP `Reason` for the connector's most recently stopped session, `unknown`
  while a session is active or none has run yet
- **Reconnect Count** (charge-point-wide, diagnostic): How many times this charge point has
  (re)connected since Home Assistant started, including automatic takeovers of a stale connection

### Switches

- **Start/Stop**: Remote-starts a transaction using the config entry's default idTag, or stops the
  connector's active transaction
- **Availability**: Sets the connector operative or inoperative. A pending ("Scheduled") change is
  not reflected until the charge point confirms it with a status update

### Buttons

- **Reset (Soft)** (charge-point-wide): Sends a Soft Reset. For a Hard reset, use the
  `ocpp.reset` service instead
- **Unlock**: Sends UnlockConnector for this connector

### Numbers

- **Power Limit**: Sets or clears the connector's charging power limit (set to `0` to clear).
  Dashboard-idiomatic alternative to the `ocpp.set_power_limit`/`ocpp.clear_power_limit` services,
  calling the same underlying command. Its value is optimistic (the last value you successfully
  set), not a live read of the charge point's actual limit — use the **Effective Power Limit**
  sensor for that. Its maximum is the **Max Power Limit** setup option, not a fixed value. It
  restores its last value across a Home Assistant restart instead of showing `unknown` again.

## Custom Services

`set_power_limit`, `clear_power_limit`, `authorize_id_token`, and the state/current-power/
effective-power-limit/availability entities above together form a documented interface meant for a
separate load-management integration to build against — see
[`docs/development/INTEROP_CONTRACT.md`](docs/development/INTEROP_CONTRACT.md) if that's you. The
services below it (`reset`, `unlock_connector`, `get_configuration`, `change_configuration`,
`trigger_message`, `get_diagnostics`) are useful operational actions but are not part of that
contract.

### `ocpp.set_power_limit`

Set a connector's charging power limit.

```yaml
service: ocpp.set_power_limit
data:
  device_id: <connector device id>
  limit_w: 7400
  phases: 3 # optional
```

### `ocpp.clear_power_limit`

Remove a connector's charging power limit.

```yaml
service: ocpp.clear_power_limit
data:
  device_id: <connector device id>
```

### `ocpp.authorize_id_token`

Check whether an idTag is authorized, without starting a transaction.

```yaml
service: ocpp.authorize_id_token
data:
  charge_point_id: CP001
  id_token: TAG001
```

`charge_point_id` alone is ambiguous if two loaded instances happen to see the same OCPP
`chargePointId`. Add an optional `device_id` (the charge point's or a connector's device) to
resolve it unambiguously — see [`CONFIGURATION.md`](docs/user/CONFIGURATION.md#ocppauthorize_id_token)
for details.

### `ocpp.reset`

Soft- or hard-reset the charge point (targets the charge-point device itself, not a connector).

```yaml
service: ocpp.reset
data:
  device_id: <charge point device id>
  reset_type: Soft # or Hard
```

### `ocpp.unlock_connector`

Ask the charge point to unlock a connector.

```yaml
service: ocpp.unlock_connector
data:
  device_id: <connector device id>
```

### `ocpp.get_configuration`

Read one or more OCPP configuration keys from the charge point (all of them if `keys` is omitted).

```yaml
service: ocpp.get_configuration
data:
  device_id: <charge point device id>
  keys: [HeartbeatInterval] # optional
```

### `ocpp.change_configuration`

Set a single OCPP configuration key on the charge point.

```yaml
service: ocpp.change_configuration
data:
  device_id: <charge point device id>
  key: HeartbeatInterval
  value: "300"
```

### `ocpp.trigger_message`

Ask the charge point to resend a specific OCPP message. Unlike the other services above, a
non-`Accepted` status (`Rejected`/`NotImplemented`) is returned as normal response data rather than
raising an error — it doesn't change any charge-point state, so it's informative ("doesn't support
that message"), not a failure.

```yaml
service: ocpp.trigger_message
data:
  device_id: <charge point device id>
  requested_message: StatusNotification
```

### `ocpp.get_diagnostics`

Ask the charge point to upload a diagnostics file to a location you provide (an FTP or HTTP(S)
server you operate — this integration does not host one itself).

```yaml
service: ocpp.get_diagnostics
data:
  device_id: <charge point device id>
  location: ftp://ops.example.com/diagnostics/
  retries: 3 # optional
  retry_interval: 30 # optional, seconds
```

## Configuration Options

### During Setup

| Name               | Required | Description                                                                                                               |
| ------------------ | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| Host               | Yes      | Address the OCPP WebSocket server listens on (default `0.0.0.0`)                                                          |
| Port               | Yes      | Port the OCPP WebSocket server listens on (default `9000`)                                                                |
| Authorization File | No       | Path to a JSON file with a static idTag allow-list. **Leaving this unset rejects every idTag**, not the other way around. |
| Default idTag      | No       | idTag used by the `start_stop` switch's remote-start command — must appear in the allow-list above                        |
| Max Power Limit    | No       | Upper bound (in watts) for the **Power Limit** number entity — match your charge point's actual maximum (default `22000`) |

Host and port are fixed once the entry is created (changing the listen address needs a new entry).
Authorization File, Default idTag, and Max Power Limit can be changed afterwards via
**Settings** → **Devices & Services** → **OCPP** → **Configure** — this reloads the entry to apply
the change.

## Troubleshooting

### Charge point does not appear

- Confirm the charge point's configured OCPP backend URL matches
  `ws://<host>:<port>/<chargePointId>` and uses subprotocol `ocpp1.6`
- Check that nothing else on the network is already bound to the configured port
- Check the Home Assistant log for connection attempts and rejected connections

### Enable Debug Logging

To enable debug logging for this integration, add the following to your `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.ocpp: debug
```

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request if you have suggestions or improvements.

You have two options to set up a development environment — expand below for full details.

<details>
<summary><strong>Development Setup</strong></summary>

Both options provide the same fully-configured environment with Home Assistant, Python 3.14, Node.js LTS, and all necessary tools.

### Option 1: GitHub Codespaces (Recommended) ☁️

Develop directly in your browser without installing anything locally!

1. Click the green **"Code"** button in this repository
2. Switch to the **"Codespaces"** tab
3. Click **"Create codespace on main"**
4. **Wait for setup** (2-3 minutes first time) — everything installs automatically
5. **Review and commit** your changes in the Source Control panel (`Ctrl+Shift+G`)

> [!TIP]
> Codespaces gives you **60 hours/month free** for personal accounts. When you start Home Assistant (`script/develop`), port 8123 forwards automatically.

### Option 2: Local Development with VS Code 💻

#### Prerequisites

You'll need these installed locally:

- **A Docker-compatible container engine** — see options by platform:

  | Option                                                                                                                   | 🍎 macOS | 🐧 Linux | 🪟 Windows | Notes                                                                                                                                                                                                                                     |
  | ------------------------------------------------------------------------------------------------------------------------ | :------: | :------: | :--------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
  | [Docker Desktop](https://www.docker.com/products/docker-desktop/)                                                        |    ✅    |    ✅    |     ✅     | **Easiest starting point for all platforms.** GUI-based, well-documented, one installer. Uses WSL2 as default backend on Windows (Hyper-V also available). Installation requires admin rights; daily use does not. Free for personal use. |
  | [OrbStack](https://orbstack.dev/) ⭐                                                                                     |    ✅    |    —     |     —      | **Recommended for macOS** once Docker Desktop feels slow. Starts in ~2s, much lighter on RAM/CPU, full Docker API compatibility. Free for personal use.                                                                                   |
  | [Docker CE](https://docs.docker.com/engine/install/) (native) ⭐                                                         |    —     |    ✅    |     —      | **Recommended for Linux.** Install directly via your package manager — no VM, no GUI, no overhead. Free.                                                                                                                                  |
  | [WSL2](https://learn.microsoft.com/windows/wsl/install) + [Docker CE](https://docs.docker.com/engine/install/ubuntu/) ⭐ |    —     |    —     |     ✅     | **Recommended for Windows** once you're comfortable with WSL2. Docker runs natively inside WSL2 — no GUI overhead. Requires one-time WSL2 setup. Free.                                                                                    |
  | [Rancher Desktop](https://rancherdesktop.io/)                                                                            |    ✅    |    ✅    |     ✅     | Open source by SUSE. GUI-based, uses WSL2 on Windows. Good alternative to Docker Desktop. Free.                                                                                                                                           |
  | [Colima](https://github.com/abiosoft/colima)                                                                             |    ✅    |    ✅    |     —      | CLI-only, very lightweight. Good for terminal-focused workflows. Free.                                                                                                                                                                    |

- **VS Code** with the [Dev Containers extension](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers)
- **Git** — macOS and Linux usually have it already; see below if not, or to get a newer version:
  - **🍎 macOS:** The system Git (`xcode-select --install`) works fine. Recommended: `brew install git` ([Homebrew](https://brew.sh/)) for a current version.
  - **🐧 Linux:** Usually pre-installed. If not: `sudo apt install git` (or your distro's equivalent).
  - **🪟 Windows + WSL2 ⭐:** Install Git _inside WSL2_ with `sudo apt install git`. Git on Windows itself is not needed — VS Code clones and operates entirely within WSL2.
  - **🪟 Windows + Docker Desktop:** Install via `winget install Git.Git` or download [Git for Windows](https://git-scm.com/download/win).
- **Hardware** — the devcontainer runs a full Home Assistant instance including Python tooling:

  |          | Minimum    | Recommended                           |
  | -------- | ---------- | ------------------------------------- |
  | **RAM**  | 8 GB       | 16 GB or more                         |
  | **CPU**  | 4 cores    | 8 cores or more                       |
  | **Disk** | 10 GB free | 20 GB free (SSD strongly recommended) |

> [!TIP]
> **Not sure which Docker option to pick?** Start with [Docker Desktop](https://www.docker.com/products/docker-desktop/) — it works on all platforms, has a GUI, and needs no extra setup. The ⭐ options are faster alternatives once you're comfortable. macOS and Linux offer the best devcontainer experience — containers run with no extra VM layer and file I/O is fast. Windows works well too; this integration uses named container volumes (files live inside WSL2, not on the Windows drive) to keep performance acceptable.

> [!NOTE]
> **New to Dev Containers?** See the [VS Code Dev Containers documentation](https://code.visualstudio.com/docs/devcontainers/containers#_system-requirements) for system requirements and how to install the extension. **Once the extension is installed, you're done** — this repository already ships a complete devcontainer configuration. You don't need to follow the rest of the VS Code guide; the setup steps below are all that's needed.

#### Setup Steps

1. **Clone in a Dev Container:**

   **🍎 macOS / 🐧 Linux:** Clone the repository and open the folder in VS Code → click **"Reopen in Container"** when prompted (or `F1` → **"Dev Containers: Reopen in Container"**).

   **🪟 Windows:** In VS Code, press `F1` → **"Dev Containers: Clone Repository in Named Container Volume..."** and enter the repository URL. This keeps files inside WSL2 for best I/O performance.

2. Wait for the container to build (2-3 minutes first time)

3. **Review and commit** changes in Source Control (`Ctrl+Shift+G`)

4. **Start developing**:

   ```bash
   script/develop  # Home Assistant runs at http://localhost:8123
   ```

> [!NOTE]
> Both Codespaces and local DevContainer provide the exact same experience. The only difference is where the container runs (GitHub's cloud vs. your machine).

</details>

---

## 🤖 AI-Assisted Development

> [!NOTE]
> **Transparency Notice:** This integration was developed with assistance from AI coding agents. AI
> assistance by itself neither guarantees nor rules out software quality. See the project's
> [`AI_POLICY.md`](AI_POLICY.md) for the policy this section follows.
>
> - **AI assistance:** substantial — the Home Assistant integration layer around the existing OCPP
>   1.6 core was built, reviewed, and debugged largely by AI agents under the maintainer's direction
> - **Human review:** partial — the maintainer directed the work and reviewed it at a high level;
>   line-by-line review of every change has not been performed
> - **Automated tests:** a `pytest-homeassistant-custom-component` suite covers the config/options
>   flow and migration, the coordinator, sensor/switch entity behavior, and all 7 services
>   (including their `ServiceValidationError` paths); the OCPP core's own test suite is not yet part
>   of this repository
> - **Real-device or service testing:** exercised end-to-end against an OCPP 1.6 charge point
>   simulator ([shiv3/ocpp-cp-simulator](https://github.com/shiv3/ocpp-cp-simulator)), not yet
>   against physical charging hardware
> - **Maturity and known limitations:** pre-1.0, actively evolving. No reauth or discovery flow yet.
>
> If you encounter unexpected behavior, please [open an issue](../../issues) on GitHub.

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

**Made with ❤️ by [@toolsfactory][user_profile]**

---

[commits-shield]: https://img.shields.io/github/commit-activity/y/toolsfactory/ocpp-ha.svg?style=for-the-badge
[commits]: https://github.com/toolsfactory/ocpp-ha/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/toolsfactory/ocpp-ha.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40toolsfactory-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/toolsfactory/ocpp-ha.svg?style=for-the-badge
[releases]: https://github.com/toolsfactory/ocpp-ha/releases
[user_profile]: https://github.com/toolsfactory
