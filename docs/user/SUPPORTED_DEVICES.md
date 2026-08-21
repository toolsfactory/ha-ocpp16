# Supported Devices

## Status

**No charge point has been validated against real hardware yet.** This project has so far only been exercised
against an OCPP 1.6 simulator (see [GETTING_STARTED.md](./GETTING_STARTED.md#prerequisites)). This page is the
structure for recording real-device results once they exist — it deliberately does not list any device as
supported before that happens (see [COMPARISON_LBBRHZN_OCPP.md](../development/COMPARISON_LBBRHZN_OCPP.md)'s
Phase 2, currently paused until hardware becomes available).

Speaking OCPP 1.6J over `ws://` (or `wss://`, see [CONFIGURATION.md](./CONFIGURATION.md#tls-certificate-wss)) is
the technical prerequisite this integration relies on — it is not by itself evidence that a specific device works,
only that it meets the baseline the protocol requires. "Not listed here" means "not yet verified," not "known to
be incompatible."

## How an entry gets added

A device is added to the table below only after someone has actually connected it and confirmed the listed
behavior — not from reading its documentation or the OCPP spec alone. If you've tried this integration with real
hardware, please [open an issue](https://github.com/toolsfactory/ocpp-ha/issues) with the details below; a
maintainer will turn it into a table row (and a regression test, if a device-specific workaround was needed).

## Device compatibility table

| Manufacturer | Model | Firmware | OCPP Version | Connectors | Authentication | Measurands | Power Limit | Reset/Unlock | Known Deviations |
| ------------ | ----- | -------- | ------------ | ---------- | -------------- | ---------- | ----------- | ------------ | ---------------- |
| _none yet_   |       |          |              |            |                |            |             |              |                  |

- **Manufacturer / Model / Firmware:** As reported in the device's own `BootNotification` (vendor, model,
  firmware version) or its physical label if `BootNotification` doesn't report it.
- **OCPP Version:** Confirmed subprotocol actually negotiated (`ocpp1.6`), not just what the device claims to
  support.
- **Connectors:** How many connectors it exposes and whether connector numbering starts at `0` or `1`.
- **Authentication:** Whether it requires a valid idTag before charging, and whether it accepts
  `RemoteStartTransaction`/`RemoteStopTransaction`.
- **Measurands:** Which `MeterValues` measurands it actually reports (energy, power, current, voltage,
  temperature, state of charge, ...) and whether they're phase-resolved.
- **Power Limit:** Whether `SetChargingProfile`/`ClearChargingProfile`/`GetCompositeSchedule` work as expected.
- **Reset/Unlock:** Whether `Reset`/`UnlockConnector` behave as the OCPP spec describes.
- **Known Deviations:** Any manufacturer-specific quirk that needed a workaround, with a link to the commit or
  regression test that addresses it — not a vague "sometimes acts up."
