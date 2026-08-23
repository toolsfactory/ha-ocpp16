# PV-Surplus Charging with Home Assistant and OCPP 1.6

This guide describes a Home Assistant control loop for charging an electric vehicle from photovoltaic (PV) surplus. It uses:

- an **EDL21 grid meter** as the authoritative control signal;
- [toolsfactory/ha-ocpp16](https://github.com/toolsfactory/ha-ocpp16) to control the charge point over OCPP 1.6;
- Huawei Solar production, battery state of charge (SOC), and battery power as supplementary inputs.

The example assumes this grid-power sign convention:

```text
Positive EDL21 power = import from the grid
Negative EDL21 power = export to the grid
```

Confirm the sign before enabling the automation. If your meter uses the opposite convention, normalize it with a template sensor or invert it everywhere in the example.

> [!WARNING]
> This is an energy-management example, not a protective device. Circuit protection, residual-current protection, cable limits, phase balancing, installation limits, and all charger/vehicle safety functions must remain enforced locally by correctly installed and configured hardware.

## Contents

- [Architecture](#architecture)
- [Prerequisites](#prerequisites)
- [Entity placeholders](#entity-placeholders)
- [Control calculation](#control-calculation)
- [Smoothing and hysteresis](#smoothing-and-hysteresis)
- [OCPP power-limit contract](#ocpp-power-limit-contract)
- [Start and stop behavior](#start-and-stop-behavior)
- [Effective-limit verification](#effective-limit-verification)
- [One-to-three-phase considerations](#one-to-three-phase-considerations)
- [Huawei battery considerations](#huawei-battery-considerations)
- [Complete Home Assistant package](#complete-home-assistant-package)
- [Setup and testing](#setup-and-testing)
- [Safety and failure handling](#safety-and-failure-handling)

## Architecture

```text
                         supplementary only
Huawei Solar ─── PV power / battery SOC / battery power ───┐
                                                           │
EDL21 grid meter ── import (+) / export (-) ────────────────┼─> Home Assistant
                                                           │   controller
OCPP current power ── actual EV charging power ─────────────┘
                                                                  │
                                                                  │ ocpp16.set_power_limit
                                                                  │ watts, optional phases
                                                                  v
                                                        Huawei SCharger / EVSE
                                                                  │
                                                                  ├─ current_power_w
                                                                  ├─ charge_point_state
                                                                  ├─ active_phases
                                                                  └─ effective_power_limit_w
```

The EDL21 meter is primary because it measures the final power exchange at the grid connection point. It automatically includes PV production, household loads, inverter losses, battery behavior, and EV charging, provided the meter is electrically upstream of all those flows.

The Huawei Solar values are useful for diagnostics and policy decisions such as “charge the home battery first.” Do not calculate surplus as `PV production - house load` when a reliable grid-point measurement is available; doing so introduces more sensors, sign conventions, update delays, and opportunities for double counting.

## Prerequisites

Before using the example, verify all of the following:

- Home Assistant receives a frequently updated EDL21 grid-power value in watts.
- Positive and negative grid-power directions are known and tested.
- `toolsfactory/ha-ocpp16` is installed and the charge point is connected to its Home Assistant OCPP WebSocket server.
- The connector exposes these OCPP entities:
  - current power;
  - charge point state;
  - effective power limit;
  - active phases;
  - start/stop transaction switch.
- The connector device ID is known. Select the **connector device**, not the charge-point parent device, when calling `ocpp16.set_power_limit`.
- The charge point accepts `SetChargingProfile` with a power schedule in watts.
- The installation's minimum and maximum usable charging powers are known.
- If remote start is required, the OCPP integration has a default idTag and an authorization file that allows that idTag. Leaving the authorization file empty rejects every idTag.
- The vehicle is present and permits charging when Home Assistant asks the start/stop switch to turn on.

The example is written as a [Home Assistant package](https://www.home-assistant.io/docs/configuration/packages/), so the helpers, template entities, and automations can live in one file.

## Entity placeholders

Replace every placeholder below before reloading the configuration.

| Placeholder                                                 | Purpose                                                                               | Required                 |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------- | ------------------------ |
| `sensor.replace_with_edl21_grid_power`                      | Grid-point power in watts; positive import, negative export                           | Yes                      |
| `sensor.replace_with_ocpp_current_power`                    | OCPP connector's actual `current_power_w` sensor                                      | Yes                      |
| `sensor.replace_with_ocpp_charge_point_state`               | OCPP connector state: `not_connected`, `ready`, `charging`, `unavailable`, or `error` | Yes                      |
| `sensor.replace_with_ocpp_effective_power_limit`            | OCPP connector's `effective_power_limit_w` sensor                                     | Recommended              |
| `sensor.replace_with_ocpp_active_phases`                    | OCPP connector's `active_phases` sensor                                               | Recommended              |
| `switch.replace_with_ocpp_start_stop`                       | OCPP connector transaction start/stop switch                                          | Required by this example |
| `sensor.replace_with_huawei_pv_power`                       | Huawei PV power for dashboards and diagnosis                                          | Optional                 |
| `sensor.replace_with_huawei_battery_soc`                    | Huawei battery SOC used by the optional start gate                                    | Optional                 |
| `sensor.replace_with_huawei_battery_charge_discharge_power` | Huawei battery power, normalized by a template sensor below                           | Optional                 |
| `REPLACE_WITH_CONNECTOR_DEVICE_ID`                          | Home Assistant device ID of the OCPP connector                                        | Yes                      |

Entity IDs are installation-specific. Find them under **Settings → Devices & services → OCPP 1.6 Central System → Devices**. The device selector in **Developer tools → Actions → `ocpp16.set_power_limit`** is the easiest way to identify the connector device ID.

## Control calculation

With positive grid import and negative grid export, the basic feedback equation is:

```text
new target power = current EV power - grid power - reserve
```

Example while exporting 2,000 W:

```text
current EV power    5,000 W
grid power         -2,000 W
reserve               200 W
----------------------------
new target power    6,800 W
```

Example after a household load causes 1,500 W of grid import:

```text
current EV power    6,800 W
grid power          1,500 W
reserve               200 W
----------------------------
new target power    5,100 W
```

When the car is not charging, current EV power is zero. The same equation becomes `export - reserve`, which is the available power used by the start decision.

The complete example also subtracts normalized Huawei battery discharge power when home-battery protection is enabled:

```text
new target = current EV power - control grid power - reserve - battery discharge
```

That extra term prevents the inverter from hiding EV demand by discharging the home battery to keep the grid meter near zero.

Every target is then:

1. limited to the configured minimum and maximum power;
2. rounded down to a 100 W step;
3. ramped upward by at most 1,000 W per control cycle;
4. sent only when it differs from the previous command by at least 300 W.

## Smoothing and hysteresis

Clouds, household loads, meter quantization, and different sensor update intervals can otherwise make the limit oscillate.

The example uses an exponential moving average (EMA) for EDL21 power:

```text
filtered = 0.35 × new reading + 0.65 × previous filtered value
```

The filtered value controls increases. Reductions use the larger of the raw and filtered grid values. Because a larger value means more import, this gives a fast response when a load appears and a slower response when new export becomes available.

Additional hysteresis is provided by:

- a 200 W default export reserve;
- a 300 W command deadband;
- a 300 W start/stop power gap;
- 120 seconds of stable surplus before starting;
- 60 seconds below the stop threshold before stopping;
- a fast stop after 20 seconds above 2,000 W grid import;
- a stop after 5 minutes below the minimum home-battery SOC, when battery-first start gating is enabled.

These are conservative starting values. Tune them using recorded meter and charger traces rather than shortening every delay at once.

## OCPP power-limit contract

The integration exposes this action:

```yaml
action: ocpp16.set_power_limit
data:
  device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
  limit_w: 7400
  phases: 3
```

Its contract is:

| Field       | Required | Meaning                                         |
| ----------- | -------- | ----------------------------------------------- |
| `device_id` | Yes      | Home Assistant device ID of one OCPP connector  |
| `limit_w`   | Yes      | Power limit in watts; must be greater than zero |
| `phases`    | No       | Requested phase count: `1`, `2`, or `3`         |

The integration sends an OCPP 1.6 `SetChargingProfile` using a connector-scoped `TxDefaultProfile`, stack level `0`, an absolute schedule, and charging-rate unit `W`. A successful call returns `{"status": "accepted"}`. Rejected, unsupported, disconnected, or otherwise failed requests raise a Home Assistant action error; they are not successful calls carrying a rejected status.

To remove the profile:

```yaml
action: ocpp16.clear_power_limit
data:
  device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
```

`clear_power_limit` also raises an error if the charge point reports that no matching profile exists. The example therefore clears only when its “last limit” helper indicates that this controller set a limit.

The service details above follow the integration's [user configuration](./CONFIGURATION.md#ocpp16set_power_limit) and [interop contract](../development/INTEROP_CONTRACT.md).

## Start and stop behavior

`ocpp16.set_power_limit` limits power; it does not start a transaction. This example uses the integration's connector start/stop switch:

```yaml
action: switch.turn_on
target:
  entity_id: switch.replace_with_ocpp_start_stop
```

The switch remote-starts with the default idTag configured in the OCPP integration. Turning it off remotely stops the connector's active transaction. Both operations can be rejected by the charge point or vehicle.

Three user modes are provided:

- **Off**: stop a controller-started transaction and clear the controller's power profile.
- **PV surplus**: start after stable surplus, regulate dynamically, and stop after sustained shortage.
- **Immediate**: set the configured maximum and start as soon as the connector is ready.

Some installations use local authorization or plug-and-charge and start automatically. In that case, remove the `switch.turn_on` actions and let the regulator take over whenever the start/stop switch reports an active transaction. Keep an installation-specific stop method if automatic stopping is still required.

The formal ha-ocpp16 load-management capability contract intentionally does not promise a generic start/release service. The start/stop switch is an integration convenience entity, so software intended to work with other OCPP integrations should treat it as optional.

## Effective-limit verification

The `effective_power_limit_w` sensor reads the charge point's actual composite schedule through OCPP `GetCompositeSchedule`.

Important behavior:

- its state is `unknown`, not zero, until the first successful read;
- it refreshes after connector-scoped events, not synchronously as part of every `set_power_limit` action;
- it can lag the last command;
- some charge points accept a profile but do not return the expected composite schedule.

Use this sensor for verification, not as the fast feedback value in the control equation. The example compares it with `input_number.wallbox_last_limit_w` and creates a persistent notification only after a mismatch greater than 500 W lasts for three minutes.

The `number` entity for the power limit is optimistic: it represents the last successfully set value, not a live schedule read. For verification, prefer `effective_power_limit_w`.

## One-to-three-phase considerations

At a nominal 230 V and the common 6 A EV minimum, approximate lower limits are:

```text
One phase:    230 V × 6 A     ≈ 1,380 W
Three phases: 230 V × 6 A × 3 ≈ 4,140 W
```

The example defaults to **4,200 W minimum and 11,000 W maximum** and deliberately omits `phases`. This is conservative for a fixed three-phase 11 kW installation.

The optional `phases` field in `ocpp16.set_power_limit` maps to OCPP's `numberPhases` schedule field. It is not, by itself, proof that the EVSE has a physical phase-switching contactor or that Huawei firmware will switch it safely. An `Accepted` profile status also does not prove that the car changed phase mode.

Only add `phases: 1` or `phases: 3` after testing the exact SCharger firmware, wiring, vehicle, and transaction behavior. Automatic 1↔3 phase changes may require stopping the transaction, waiting for current to reach zero, changing the EVSE mode through a device-specific interface, and starting again. Do not implement that sequence by merely changing `numberPhases` every ten seconds.

The `active_phases` sensor is a verification aid. It counts phases whose OCPP `Current.Import` value is above zero and exposes `phase_l1_a`, `phase_l2_a`, and `phase_l3_a` attributes. It may be `unknown`, lagging, or incomplete if the charger does not report per-phase current.

For a tested fixed one-phase setup, change `input_number.wallbox_min_charge_power_w` to approximately `1400` and set an appropriate one-phase maximum. For fixed three-phase charging, retain approximately `4200` or the minimum required by the charger/vehicle pair.

## Huawei battery considerations

The grid meter already includes battery charging and discharging. Do not blindly add Huawei battery power to a calculated “PV surplus,” because that can count the same energy twice.

There are two useful battery policies:

1. **Battery-first start gate**: set `input_number.wallbox_min_battery_soc` above zero. PV charging will start only after the Huawei SOC reaches that value. A value of zero disables the gate.
2. **Prevent battery-to-car discharge**: keep `input_boolean.wallbox_protect_home_battery` on. The example converts Huawei battery power into a positive discharge value and subtracts it from the EV target.

The template in this guide assumes the commonly reported Huawei “battery charge/discharge power” convention:

```text
Positive = battery charging
Negative = battery discharging
```

Verify this on your installation. Observe the sensor once while the battery is clearly charging and once while it is clearly discharging. If your sensor reports discharge as positive, remove the leading minus sign in the normalization template.

Huawei PV power is intentionally not used in the feedback equation. It is valuable for dashboards, diagnosis, and plausibility checks, but the EDL21 meter remains the final authority.

If Huawei battery data becomes unavailable, the example treats battery discharge as zero but still protects against grid import through EDL21. If strict battery protection is required, extend the fail-safe automation so missing Huawei battery data also selects **Off**.

## Complete Home Assistant package

Save the following as `/config/packages/pv_surplus_charging.yaml`. Replace all entity and device placeholders first.

```yaml
input_select:
  wallbox_charging_mode:
    name: Wallbox charging mode
    options:
      - "Off"
      - "PV surplus"
      - "Immediate"
    initial: "Off"

input_boolean:
  wallbox_grid_filter_initialized:
    name: Wallbox grid filter initialized
    initial: false
  wallbox_protect_home_battery:
    name: Protect home battery while EV charging
    initial: true

input_number:
  wallbox_filtered_grid_power_w:
    name: Wallbox filtered grid power
    min: -30000
    max: 30000
    step: 1
    unit_of_measurement: W
    mode: box

  wallbox_last_limit_w:
    name: Wallbox last requested power limit
    min: 0
    max: 22000
    step: 100
    unit_of_measurement: W
    mode: box

  wallbox_min_charge_power_w:
    name: Wallbox minimum charging power
    min: 1000
    max: 22000
    step: 100
    initial: 4200
    unit_of_measurement: W
    mode: box

  wallbox_max_charge_power_w:
    name: Wallbox maximum charging power
    min: 1000
    max: 22000
    step: 100
    initial: 11000
    unit_of_measurement: W
    mode: box

  wallbox_grid_reserve_w:
    name: Wallbox grid export reserve
    min: 0
    max: 2000
    step: 50
    initial: 200
    unit_of_measurement: W
    mode: box

  wallbox_min_battery_soc:
    name: Wallbox minimum home battery SOC
    min: 0
    max: 100
    step: 1
    initial: 0
    unit_of_measurement: "%"
    mode: slider

template:
  - sensor:
      - name: Wallbox battery discharge power
        unique_id: wallbox_battery_discharge_power
        device_class: power
        state_class: measurement
        unit_of_measurement: W
        availability: >-
          {{ states('sensor.replace_with_huawei_battery_charge_discharge_power')
             | is_number }}
        state: >-
          {% set battery_power =
               states('sensor.replace_with_huawei_battery_charge_discharge_power')
               | float(0) %}
          {{ [0, -battery_power] | max | round(0) }}

  - binary_sensor:
      - name: Wallbox grid meter healthy
        unique_id: wallbox_grid_meter_healthy
        device_class: connectivity
        state: >-
          {% set grid = states.sensor.replace_with_edl21_grid_power %}
          {% if grid is none %}
            {{ false }}
          {% else %}
            {% set age = as_timestamp(now()) - as_timestamp(grid.last_reported, 0) %}
            {{ grid.state | is_number and age < 45 }}
          {% endif %}

automation:
  - id: wallbox_update_filtered_grid_power
    alias: "Wallbox: update filtered EDL21 grid power"
    mode: single
    triggers:
      - trigger: homeassistant
        event: start
        id: start
      - trigger: time_pattern
        seconds: "/10"
        id: tick
    actions:
      - if:
          - condition: template
            value_template: "{{ trigger.id == 'start' }}"
        then:
          - action: input_boolean.turn_off
            target:
              entity_id: input_boolean.wallbox_grid_filter_initialized

      - condition: template
        value_template: >-
          {{ states('sensor.replace_with_edl21_grid_power') | is_number }}

      - variables:
          raw_grid_w: >-
            {{ states('sensor.replace_with_edl21_grid_power') | float }}
          previous_filtered_w: >-
            {{ states('input_number.wallbox_filtered_grid_power_w')
               | float(raw_grid_w) }}
          filtered_grid_w: >-
            {% if is_state('input_boolean.wallbox_grid_filter_initialized', 'on') %}
              {{ (0.35 * raw_grid_w + 0.65 * previous_filtered_w) | round(0) }}
            {% else %}
              {{ raw_grid_w | round(0) }}
            {% endif %}

      - action: input_number.set_value
        target:
          entity_id: input_number.wallbox_filtered_grid_power_w
        data:
          value: "{{ filtered_grid_w }}"

      - action: input_boolean.turn_on
        target:
          entity_id: input_boolean.wallbox_grid_filter_initialized

  - id: wallbox_apply_charging_mode
    alias: "Wallbox: apply charging mode"
    mode: restart
    triggers:
      - trigger: state
        entity_id: input_select.wallbox_charging_mode
      - trigger: state
        entity_id: sensor.replace_with_ocpp_charge_point_state
        to: "ready"
      - trigger: homeassistant
        event: start
    actions:
      - choose:
          - conditions:
              - condition: state
                entity_id: input_select.wallbox_charging_mode
                state: "Off"
            sequence:
              - if:
                  - condition: state
                    entity_id: switch.replace_with_ocpp_start_stop
                    state: "on"
                then:
                  - action: switch.turn_off
                    target:
                      entity_id: switch.replace_with_ocpp_start_stop

              - if:
                  - condition: numeric_state
                    entity_id: input_number.wallbox_last_limit_w
                    above: 0
                then:
                  - action: ocpp16.clear_power_limit
                    data:
                      device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
                  - action: input_number.set_value
                    target:
                      entity_id: input_number.wallbox_last_limit_w
                    data:
                      value: 0

          - conditions:
              - condition: state
                entity_id: input_select.wallbox_charging_mode
                state: "Immediate"
            sequence:
              - variables:
                  immediate_limit_w: >-
                    {{ states('input_number.wallbox_max_charge_power_w') | int }}
              - action: ocpp16.set_power_limit
                data:
                  device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
                  limit_w: "{{ immediate_limit_w }}"
              - action: input_number.set_value
                target:
                  entity_id: input_number.wallbox_last_limit_w
                data:
                  value: "{{ immediate_limit_w }}"
              - if:
                  - condition: state
                    entity_id: sensor.replace_with_ocpp_charge_point_state
                    state: "ready"
                  - condition: state
                    entity_id: switch.replace_with_ocpp_start_stop
                    state: "off"
                then:
                  - action: switch.turn_on
                    target:
                      entity_id: switch.replace_with_ocpp_start_stop

  - id: wallbox_enforce_off_mode
    alias: "Wallbox: enforce off mode"
    mode: single
    triggers:
      - trigger: state
        entity_id: switch.replace_with_ocpp_start_stop
        to: "on"
    conditions:
      - condition: state
        entity_id: input_select.wallbox_charging_mode
        state: "Off"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.replace_with_ocpp_start_stop

  - id: wallbox_start_on_pv_surplus
    alias: "Wallbox: start on stable PV surplus"
    mode: single
    triggers:
      - trigger: template
        value_template: >-
          {% set filtered_grid_w =
               states('input_number.wallbox_filtered_grid_power_w') | float(0) %}
          {% set reserve_w =
               states('input_number.wallbox_grid_reserve_w') | float(0) %}
          {% set minimum_w =
               states('input_number.wallbox_min_charge_power_w') | float(4200) %}
          {% set minimum_soc =
               states('input_number.wallbox_min_battery_soc') | float(0) %}
          {% set battery_soc =
               states('sensor.replace_with_huawei_battery_soc') %}
          {% set soc_ok = minimum_soc == 0
             or (battery_soc | is_number
                 and battery_soc | float >= minimum_soc) %}
          {{ is_state('input_select.wallbox_charging_mode', 'PV surplus')
             and is_state('binary_sensor.wallbox_grid_meter_healthy', 'on')
             and is_state('sensor.replace_with_ocpp_charge_point_state', 'ready')
             and is_state('switch.replace_with_ocpp_start_stop', 'off')
             and soc_ok
             and (-filtered_grid_w - reserve_w) >= (minimum_w + 300) }}
        for: "00:02:00"
    actions:
      - variables:
          available_w: >-
            {{ -(states('input_number.wallbox_filtered_grid_power_w') | float(0))
               - states('input_number.wallbox_grid_reserve_w') | float(0) }}
          minimum_w: >-
            {{ states('input_number.wallbox_min_charge_power_w') | float(4200) }}
          maximum_w: >-
            {{ states('input_number.wallbox_max_charge_power_w') | float(11000) }}
          start_limit_w: >-
            {% set bounded = [[available_w, minimum_w] | max, maximum_w] | min %}
            {{ ((bounded / 100) | round(0, 'floor') * 100) | int }}

      - action: ocpp16.set_power_limit
        data:
          device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
          limit_w: "{{ start_limit_w }}"

      - action: input_number.set_value
        target:
          entity_id: input_number.wallbox_last_limit_w
        data:
          value: "{{ start_limit_w }}"

      - action: switch.turn_on
        target:
          entity_id: switch.replace_with_ocpp_start_stop

  - id: wallbox_regulate_pv_surplus
    alias: "Wallbox: regulate PV surplus power"
    mode: single
    max_exceeded: silent
    triggers:
      - trigger: time_pattern
        seconds: "/10"
    conditions:
      - condition: state
        entity_id: input_select.wallbox_charging_mode
        state: "PV surplus"
      - condition: state
        entity_id: switch.replace_with_ocpp_start_stop
        state: "on"
      - condition: state
        entity_id: binary_sensor.wallbox_grid_meter_healthy
        state: "on"
      - condition: template
        value_template: >-
          {{ states('sensor.replace_with_ocpp_current_power') | is_number }}
    actions:
      - variables:
          raw_grid_w: >-
            {{ states('sensor.replace_with_edl21_grid_power') | float }}
          filtered_grid_w: >-
            {{ states('input_number.wallbox_filtered_grid_power_w') | float }}
          control_grid_w: "{{ [raw_grid_w, filtered_grid_w] | max }}"
          measured_ev_w: >-
            {{ states('sensor.replace_with_ocpp_current_power') | float }}
          reserve_w: >-
            {{ states('input_number.wallbox_grid_reserve_w') | float(0) }}
          battery_discharge_w: >-
            {% if is_state('input_boolean.wallbox_protect_home_battery', 'on') %}
              {{ states('sensor.wallbox_battery_discharge_power') | float(0) }}
            {% else %}
              0
            {% endif %}
          minimum_w: >-
            {{ states('input_number.wallbox_min_charge_power_w') | float(4200) }}
          maximum_w: >-
            {{ states('input_number.wallbox_max_charge_power_w') | float(11000) }}
          previous_limit_w: >-
            {{ states('input_number.wallbox_last_limit_w') | float(minimum_w) }}
          raw_target_w: >-
            {{ measured_ev_w - control_grid_w - reserve_w
               - battery_discharge_w }}
          bounded_target_w: >-
            {{ [[raw_target_w, minimum_w] | max, maximum_w] | min }}
          stepped_target_w: >-
            {{ ((bounded_target_w / 100) | round(0, 'floor') * 100) | int }}
          requested_limit_w: >-
            {% if stepped_target_w > previous_limit_w %}
              {{ [stepped_target_w, previous_limit_w + 1000] | min | int }}
            {% else %}
              {{ stepped_target_w | int }}
            {% endif %}

      - condition: template
        value_template: >-
          {{ (requested_limit_w | float - previous_limit_w | float) | abs >= 300 }}

      - action: ocpp16.set_power_limit
        data:
          device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
          limit_w: "{{ requested_limit_w }}"

      - action: input_number.set_value
        target:
          entity_id: input_number.wallbox_last_limit_w
        data:
          value: "{{ requested_limit_w }}"

  - id: wallbox_stop_on_insufficient_surplus
    alias: "Wallbox: stop when PV surplus is insufficient"
    mode: single
    triggers:
      - trigger: template
        id: low_surplus
        value_template: >-
          {% set current_w = states('sensor.replace_with_ocpp_current_power') %}
          {% set raw_grid_w =
               states('sensor.replace_with_edl21_grid_power') | float(0) %}
          {% set filtered_grid_w =
               states('input_number.wallbox_filtered_grid_power_w') | float(0) %}
          {% set control_grid_w = [raw_grid_w, filtered_grid_w] | max %}
          {% set reserve_w =
               states('input_number.wallbox_grid_reserve_w') | float(0) %}
          {% set minimum_w =
               states('input_number.wallbox_min_charge_power_w') | float(4200) %}
          {% set battery_discharge_w =
               states('sensor.wallbox_battery_discharge_power') | float(0)
               if is_state('input_boolean.wallbox_protect_home_battery', 'on')
               else 0 %}
          {{ is_state('input_select.wallbox_charging_mode', 'PV surplus')
             and is_state('switch.replace_with_ocpp_start_stop', 'on')
             and current_w | is_number
             and (current_w | float - control_grid_w - reserve_w
                  - battery_discharge_w) < (minimum_w - 300) }}
        for: "00:01:00"

      - trigger: numeric_state
        id: severe_import
        entity_id: sensor.replace_with_edl21_grid_power
        above: 2000
        for: "00:00:20"

      - trigger: template
        id: battery_reserve
        value_template: >-
          {% set minimum_soc =
               states('input_number.wallbox_min_battery_soc') | float(0) %}
          {% set battery_soc = states('sensor.replace_with_huawei_battery_soc') %}
          {{ is_state('input_select.wallbox_charging_mode', 'PV surplus')
             and is_state('switch.replace_with_ocpp_start_stop', 'on')
             and minimum_soc > 0
             and battery_soc | is_number
             and battery_soc | float < (minimum_soc - 5) }}
        for: "00:05:00"
    conditions:
      - condition: state
        entity_id: input_select.wallbox_charging_mode
        state: "PV surplus"
      - condition: state
        entity_id: switch.replace_with_ocpp_start_stop
        state: "on"
    actions:
      - action: switch.turn_off
        target:
          entity_id: switch.replace_with_ocpp_start_stop

      - action: ocpp16.clear_power_limit
        data:
          device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID

      - action: input_number.set_value
        target:
          entity_id: input_number.wallbox_last_limit_w
        data:
          value: 0

  - id: wallbox_fail_safe_on_bad_input
    alias: "Wallbox: fail safe on missing control data"
    mode: single
    triggers:
      - trigger: time_pattern
        seconds: "/10"
    conditions:
      - condition: state
        entity_id: input_select.wallbox_charging_mode
        state: "PV surplus"
      - condition: template
        value_template: >-
          {% set transaction_active =
               is_state('switch.replace_with_ocpp_start_stop', 'on') %}
          {% set transaction_age = as_timestamp(now())
             - as_timestamp(states.switch.replace_with_ocpp_start_stop.last_changed, 0) %}
          {% set current_power_missing = transaction_active
             and transaction_age > 60
             and not (states('sensor.replace_with_ocpp_current_power') | is_number) %}
          {% set connector_fault =
               states('sensor.replace_with_ocpp_charge_point_state')
               in ['unavailable', 'unknown', 'error'] %}
          {{ not is_state('binary_sensor.wallbox_grid_meter_healthy', 'on')
             or current_power_missing
             or connector_fault }}
    actions:
      - action: input_select.select_option
        target:
          entity_id: input_select.wallbox_charging_mode
        data:
          option: "Off"

      - action: persistent_notification.create
        data:
          notification_id: wallbox_pv_controller_fail_safe
          title: Wallbox PV controller stopped
          message: >-
            PV-surplus charging was switched off because the grid meter,
            OCPP power value, or connector state was not usable. Check the
            EDL21 and OCPP entities before enabling PV surplus mode again.

  - id: wallbox_verify_effective_power_limit
    alias: "Wallbox: verify effective OCPP power limit"
    mode: single
    triggers:
      - trigger: template
        value_template: >-
          {% set effective =
               states('sensor.replace_with_ocpp_effective_power_limit') %}
          {% set requested =
               states('input_number.wallbox_last_limit_w') | float(0) %}
          {{ is_state('switch.replace_with_ocpp_start_stop', 'on')
             and effective | is_number
             and requested > 0
             and (effective | float - requested) | abs > 500 }}
        for: "00:03:00"
    actions:
      - action: persistent_notification.create
        data:
          notification_id: wallbox_effective_limit_mismatch
          title: Wallbox power-limit mismatch
          message: >-
            Requested {{ states('input_number.wallbox_last_limit_w') | int }} W,
            but GetCompositeSchedule reports
            {{ states('sensor.replace_with_ocpp_effective_power_limit') }} W.
            Check the charger log, OCPP status, and firmware behavior.
```

If packages are not enabled, add this to `configuration.yaml` and restart Home Assistant:

```yaml
homeassistant:
  packages: !include_dir_named packages
```

### Optional explicit phase request

After successful hardware testing, add `phases` to every `ocpp16.set_power_limit` call. For a fixed three-phase setup:

```yaml
- action: ocpp16.set_power_limit
  data:
    device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
    limit_w: "{{ requested_limit_w }}"
    phases: 3
```

Do not add this field only to one branch; start, regulation, and immediate mode should request phases consistently.

## Setup and testing

### 1. Record the existing entities

Create a small table with the real entity IDs and the connector device ID. Confirm that OCPP current power is in watts and that the state sensor changes between `ready` and `charging` as expected.

### 2. Verify the EDL21 sign

With PV production low, turn on a known household load. The EDL21 value must become positive. During clear export, it must become negative. If not, normalize the sensor before proceeding.

### 3. Test the OCPP action manually

With the cable connected, call:

```yaml
action: ocpp16.set_power_limit
data:
  device_id: REPLACE_WITH_CONNECTOR_DEVICE_ID
  limit_w: 4200
```

Confirm:

- the action succeeds;
- the car charges at approximately the requested power;
- `current_power_w` updates;
- `effective_power_limit_w` eventually reports approximately 4,200 W;
- `active_phases` and its phase-current attributes are plausible.

Then call `ocpp16.clear_power_limit` and confirm the profile is removed.

### 4. Test start and stop manually

Configure the integration's default idTag and authorization file. With the cable connected and the state `ready`, turn on the start/stop switch. Confirm that a transaction starts. Turn it off and confirm that the same transaction stops.

If the start is rejected, inspect the idTag authorization, vehicle state, connector state, and charge-point logs before enabling automation.

### 5. Install the package with a safe maximum

Replace all placeholders, start with a conservative maximum such as 4,200 W, run Home Assistant's configuration check, and restart. Confirm that the charging mode initializes to **Off**.

### 6. Test immediate mode

Select **Immediate** with the maximum still set low. Confirm the profile, start/stop switch, actual power, and effective-limit sensor all behave as documented. Return to **Off** and confirm the transaction stops and the profile clears.

### 7. Test PV-surplus mode without a vehicle start

Keep the connector unavailable or the cable unplugged. Observe:

- raw EDL21 power;
- `input_number.wallbox_filtered_grid_power_w`;
- `binary_sensor.wallbox_grid_meter_healthy`;
- Huawei battery discharge normalization.

Check the calculation manually from history graphs.

### 8. Test with the vehicle

Start with a large, stable surplus and watch the two-minute start delay. Switch on a household load and confirm that the limit decreases quickly. Remove the load and confirm that the limit rises gradually. Reduce PV surplus below the minimum and confirm the one-minute stop delay.

### 9. Tune one parameter at a time

Recommended tuning order:

1. minimum and maximum charging power;
2. EDL21 sign and update interval;
3. grid reserve;
4. battery protection sign and SOC threshold;
5. start and stop delays;
6. EMA coefficient, deadband, and upward ramp.

## Safety and failure handling

### What the example handles

- Invalid or stale EDL21 data selects **Off**.
- Missing OCPP current power during an active transaction selects **Off**.
- An unavailable or faulted connector state selects **Off**.
- A sustained large grid import stops PV charging.
- Every command is bounded by configured minimum and maximum power.
- A persistent notification reports fail-safe stops and effective-limit mismatches.
- Service rejections remain visible as Home Assistant automation errors.

### Important limitations

- A Home Assistant automation cannot stop the charger if Home Assistant is down, the network is broken, or the charge point is disconnected.
- The OCPP `TxDefaultProfile` has no end time in this integration and can remain active until cleared. If Home Assistant stops, the last accepted limit may remain in effect and charging may continue at that limit.
- If remote stop is rejected, the automation run stops at that action and does not proceed to clear the profile. This ordering intentionally avoids removing the cap from a transaction that could not be stopped.
- `SetChargingProfile: Accepted` confirms protocol acceptance, not measured electrical compliance. Verify actual power and the composite schedule.
- Sensor update delays can still cause brief grid import. Increase the reserve or reduce the control interval only after measuring real behavior.
- The EDL21 meter must cover the whole site. A meter that excludes the battery, wallbox, or part of the household cannot provide a correct site-level control signal.
- Home Assistant and OCPP are not substitutes for a certified dynamic load-management system when one is legally or electrically required.

### Recommended hardware-side safeguards

- Configure the EVSE's permanent maximum current/power to the installation limit.
- Keep local overcurrent and residual-current protection independent of Home Assistant.
- Configure charger behavior for communication loss conservatively if the firmware supports it.
- Keep Huawei battery reserve and discharge limits appropriate for the installation.
- Review per-phase currents, especially on a one-phase setup or an installation with strict phase-imbalance limits.
- Test power loss, Home Assistant restart, OCPP disconnect, EDL21 failure, vehicle unplug, and charger rejection before unattended use.

## Related documentation

- [Getting started with ha-ocpp16](./GETTING_STARTED.md)
- [ha-ocpp16 configuration and actions](./CONFIGURATION.md)
- [ha-ocpp16 interop contract](../development/INTEROP_CONTRACT.md)
- [Huawei Solar Home Assistant integration](https://github.com/wlcrs/huawei_solar)
