# OCPP 1.6 Central System

[![GitHub Release][releases-shield]][releases]
[![GitHub Activity][commits-shield]][commits]
[![License][license-shield]](LICENSE)

[![hacs][hacsbadge]][hacs]
![Project Maintenance][maintenance-shield]

**✨ Develop in the cloud:** Want to contribute or customize this integration? Open it directly in GitHub Codespaces - no local setup required!

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/toolsfactory/ha-ocpp16?quickstart=1)

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
- **Restart-Safe Diagnostics**: Transaction ID, session duration/energy, stop reason, and reconnect
  count all restore their last known value across a Home Assistant restart
- **Static Authorization**: An optional JSON allow-list of idTags a charge point may accept for
  transactions
- **Direct `wss://`**: Optional built-in TLS, no reverse proxy required
- **Custom Services**: Set/clear a connector's power limit, check an idTag's authorization status,
  and drive OCPP operational actions (reset, unlock, configuration, diagnostics) from automations

**This integration sets up the following platforms.**

| Platform | Description                                                                                |
| -------- | ------------------------------------------------------------------------------------------ |
| `sensor` | Connector state, current charging power, effective power limit, and per-measurand readings |
| `switch` | Start/stop a transaction, and toggle a connector operative/inoperative                     |
| `number` | Charging power limit                                                                       |
| `button` | Soft reset, unlock connector                                                               |

Each charge point becomes a Home Assistant device, with every connector as its own sub-device.

## 🚀 Quick Start

**Prerequisites:** [HACS](https://hacs.xyz/) installed, and an OCPP 1.6 charge point or simulator
(e.g. [shiv3/ocpp-cp-simulator](https://github.com/shiv3/ocpp-cp-simulator)).

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=toolsfactory&repository=ha-ocpp16&category=integration)

1. Click above to open this repository in HACS → **Download** → **restart Home Assistant**
2. [![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=ocpp16)
   click above (or **Settings** → **Devices & Services** → **+ Add Integration** → search "OCPP 1.6
   Central System") and enter the listen address/port for the WebSocket server
3. Point your charge point's OCPP backend URL at `ws://<host>:<port>/<chargePointId>`

Devices and entities appear automatically the moment a charge point connects and sends its first
`BootNotification` — nothing to pre-register. Full walkthrough, manual installation, and every setup
option: [**GETTING_STARTED.md**](docs/user/GETTING_STARTED.md).

## Available Entities

Most entities are created per connector as soon as a charge point reports it; a few are
charge-point-wide instead. Full descriptions, restore-across-restart behavior, and entity naming:
[**GETTING_STARTED.md**](docs/user/GETTING_STARTED.md#what-gets-created).

- **Sensors:** charge point state, current power, effective power limit, active phases, dynamic
  per-measurand sensors, last heartbeat, transaction ID, session duration/energy, stop reason,
  reconnect count
- **Switches:** start/stop transaction, availability (operative/inoperative)
- **Buttons:** soft reset, unlock connector
- **Numbers:** power limit

## Custom Services

Nine services, exposed as `ocpp16.<name>`. `set_power_limit`, `clear_power_limit`,
`authorize_id_token`, plus the state/current-power/effective-power-limit/availability entities above,
together form a documented interface meant for a separate load-management integration to build
against — see [**INTEROP_CONTRACT.md**](docs/development/INTEROP_CONTRACT.md) if that's you. The rest
(`reset`, `unlock_connector`, `get_configuration`, `change_configuration`, `trigger_message`,
`get_diagnostics`) are operational actions outside that contract.

| Service                                                                         | Purpose                                                    |
| ------------------------------------------------------------------------------- | ---------------------------------------------------------- |
| [`set_power_limit`](docs/user/CONFIGURATION.md#ocpp16set_power_limit)           | Set a connector's charging power limit                     |
| [`clear_power_limit`](docs/user/CONFIGURATION.md#ocpp16clear_power_limit)       | Remove a connector's charging power limit                  |
| [`authorize_id_token`](docs/user/CONFIGURATION.md#ocpp16authorize_id_token)     | Check whether an idTag is authorized, without starting one |
| [`reset`](docs/user/CONFIGURATION.md#ocpp16reset)                               | Soft- or hard-reset the charge point                       |
| [`unlock_connector`](docs/user/CONFIGURATION.md#ocpp16unlock_connector)         | Ask the charge point to unlock a connector                 |
| [`get_configuration`](docs/user/CONFIGURATION.md#ocpp16get_configuration)       | Read one or more OCPP configuration keys                   |
| [`change_configuration`](docs/user/CONFIGURATION.md#ocpp16change_configuration) | Set a single OCPP configuration key                        |
| [`trigger_message`](docs/user/CONFIGURATION.md#ocpp16trigger_message)           | Ask the charge point to resend a specific OCPP message     |
| [`get_diagnostics`](docs/user/CONFIGURATION.md#ocpp16get_diagnostics)           | Ask the charge point to upload a diagnostics file          |

Full YAML examples, response shapes, and error behavior for every service:
[**CONFIGURATION.md**](docs/user/CONFIGURATION.md#services). More automation/dashboard
examples: [**EXAMPLES.md**](docs/user/EXAMPLES.md).

## Configuration Options

Host, port, an optional TLS certificate pair for direct `wss://`, an optional static idTag
allow-list, a default idTag, and a max power limit — all set during initial setup and changeable
afterward without recreating the entry. Full reference, including the authorization file format and
what each option does: [**CONFIGURATION.md**](docs/user/CONFIGURATION.md#initial-setup-options).

## Troubleshooting

- **Charge point does not appear:** confirm its OCPP backend URL matches
  `ws://<host>:<port>/<chargePointId>` (or `wss://`) with subprotocol `ocpp1.6`, that nothing else is
  bound to the configured port, and check the Home Assistant log for rejected connections.
- **Enable debug logging:**

  ```yaml
  logger:
    default: info
    logs:
      custom_components.ocpp16: debug
  ```

More: [**CONFIGURATION.md** troubleshooting section](docs/user/CONFIGURATION.md#config-entry-fails-to-load).

## 🤝 Contributing

Contributions are welcome! Please open an issue or pull request if you have suggestions or improvements.

You have two options to set up a development environment — expand below for full details.

<details>
<summary><strong>Development Setup</strong></summary>

Both options provide the same fully-configured environment with Home Assistant, Python 3.14, Node.js LTS, and all necessary tools.

### Option 1: GitHub Codespaces (Recommended) ☁️

Develop directly in your browser without installing anything locally! Click the green **"Code"**
button in this repository → **"Codespaces"** tab → **"Create codespace on main"**, then run
`script/develop` once setup finishes. Full guide, including Copilot Agent PR testing:
[**CODESPACES.md**](docs/development/CODESPACES.md).

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
> - **AI assistance:** substantial — both the standalone OCPP 1.6 core and the Home Assistant
>   integration layer around it were built, reviewed, and debugged largely by AI agents under the
>   maintainer's direction
> - **Human review:** partial — the maintainer directed the work and reviewed it at a high level;
>   line-by-line review of every change has not been performed
> - **Automated tests:** a `pytest-homeassistant-custom-component` suite (235 tests, 93% coverage,
>   enforced by CI) covers the config/options flow and migration, the coordinator, sensor/switch/
>   button/number entity behavior, all 9 services (including their `ServiceValidationError` paths),
>   and the standalone core (OCPP protocol handlers, the WebSocket transport over both `ws://` and
>   `wss://`, and the interactive console)
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

[commits-shield]: https://img.shields.io/github/commit-activity/y/toolsfactory/ha-ocpp16.svg?style=for-the-badge
[commits]: https://github.com/toolsfactory/ha-ocpp16/commits/main
[hacs]: https://github.com/hacs/integration
[hacsbadge]: https://img.shields.io/badge/HACS-Default-orange.svg?style=for-the-badge
[license-shield]: https://img.shields.io/github/license/toolsfactory/ha-ocpp16.svg?style=for-the-badge
[maintenance-shield]: https://img.shields.io/badge/maintainer-%40toolsfactory-blue.svg?style=for-the-badge
[releases-shield]: https://img.shields.io/github/release/toolsfactory/ha-ocpp16.svg?style=for-the-badge
[releases]: https://github.com/toolsfactory/ha-ocpp16/releases
[user_profile]: https://github.com/toolsfactory
