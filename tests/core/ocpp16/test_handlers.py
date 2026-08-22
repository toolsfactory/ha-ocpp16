"""Tests for `core/ocpp16/handlers.py`'s `ChargePointHandler`.

No test elsewhere in this suite instantiates `ChargePointHandler` directly -- every other test
drives the domain stores directly (`boot_charge_point` et al.) or mocks the `ChargePointConnection`
Protocol (`mock_charge_point_connection`), bypassing this file entirely. These tests fill that gap:
inbound `on_*` handlers are called directly (python-ocpp's `@on` decorator only tags metadata, it
doesn't change the calling convention) against a real `HandlerServices` built from real, empty
domain stores; outbound Central-System-initiated methods patch `self.call` with a canned
`ocpp_call_result` and verify the request built and the response parsed -- python-ocpp's own
`call()`/wire mechanics are a trusted third-party dependency, not re-tested here (Phase 5's real
localhost transport test covers one full round trip at that lower level instead).

`_build_handler` returns the `HandlerServices`/connection alongside the handler instead of tests
reaching into `handler._services`/`handler._connection` -- this project's ruff config does not
exempt `tests/*` from `SLF001` (private member access), unlike `S101`/`PLR2004`/`D`/`PTH`.
"""

from datetime import UTC
from unittest.mock import AsyncMock

from ocpp.v16 import call_result as ocpp_call_result, enums as ocpp_enums
import pytest

from custom_components.ocpp16.core.domain.authorization import StaticAuthorizationProvider, StaticIdTagEntry
from custom_components.ocpp16.core.domain.commands import ChargePointCallRejectedError
from custom_components.ocpp16.core.domain.connector_state import ConnectorStateStore
from custom_components.ocpp16.core.domain.events import EventBus
from custom_components.ocpp16.core.domain.meter_values import MeterValueStore
from custom_components.ocpp16.core.domain.models import StateChangeEvent
from custom_components.ocpp16.core.domain.registry import ChargePointRegistryStore
from custom_components.ocpp16.core.domain.transactions import TransactionManager
from custom_components.ocpp16.core.logging_setup import get_charge_point_logger
from custom_components.ocpp16.core.ocpp16.handlers import (
    ChargePointHandler,
    HandlerServices,
    _expect_response,
    _extract_meter_samples,
    _log_handler_errors,
    _mask_id_tag,
    _parse_timestamp,
)

CHARGE_POINT_ID = "CP001"


def _build_handler(
    authorization: StaticAuthorizationProvider | None = None,
) -> tuple[ChargePointHandler, HandlerServices, AsyncMock]:
    services = HandlerServices(
        registry=ChargePointRegistryStore(),
        connectors=ConnectorStateStore(),
        transactions=TransactionManager(),
        meter_values=MeterValueStore(),
        authorization=authorization or StaticAuthorizationProvider.empty(),
        events=EventBus(),
        heartbeat_interval_seconds=300,
        heartbeat_grace_period_seconds=5.0,
    )
    connection = AsyncMock()
    handler = ChargePointHandler(
        CHARGE_POINT_ID, connection, services=services, cp_logger=get_charge_point_logger(CHARGE_POINT_ID)
    )
    # transport.py's _run_connection() always registers the connection before any OCPP message
    # (including the first Heartbeat) can arrive -- mark_heartbeat is a no-op otherwise.
    services.registry.register_connection(CHARGE_POINT_ID, handler)
    return handler, services, connection


# -- Module-level helpers -----------------------------------------------------


def test_expect_response_raises_on_a_suppressed_call_error() -> None:
    """`call(..., suppress=True)` returns `None` on a CallError -- that must not look like success."""
    with pytest.raises(ChargePointCallRejectedError):
        _expect_response(None)


def test_expect_response_passes_through_a_real_response() -> None:
    """A real response is returned unchanged."""
    response = ocpp_call_result.Reset(status="Accepted")
    assert _expect_response(response) is response


def test_mask_id_tag_fully_masks_short_tags() -> None:
    """A 4-characters-or-shorter idTag is fully masked -- there's nothing safe to reveal."""
    assert _mask_id_tag("AB12") == "****"


def test_mask_id_tag_keeps_the_last_four_characters_of_longer_tags() -> None:
    """Longer idTags keep only their last 4 characters visible in logs."""
    assert _mask_id_tag("DEADBEEF1234") == "********1234"


def test_parse_timestamp_assumes_utc_when_no_offset_is_given() -> None:
    """An OCPP timestamp without a timezone offset is treated as UTC, not left naive."""
    parsed = _parse_timestamp("2026-08-21T10:00:00")

    assert parsed.tzinfo is UTC


def test_parse_timestamp_keeps_an_explicit_offset() -> None:
    """A timestamp that already carries a timezone offset is not overridden."""
    parsed = _parse_timestamp("2026-08-21T10:00:00Z")

    assert parsed.utcoffset() is not None


async def test_log_handler_errors_logs_and_reraises(caplog: pytest.LogCaptureFixture) -> None:
    """An unhandled exception in a handler is logged with context before re-raising (REQ-0031 AC4)."""
    handler, _services, _connection = _build_handler()

    @_log_handler_errors
    async def _failing_handler(self: ChargePointHandler) -> None:
        raise ValueError("boom")

    with pytest.raises(ValueError, match="boom"):
        await _failing_handler(handler)
    assert "Unbehandelter Fehler" in caplog.text


def test_heartbeat_timeout_seconds_is_twice_the_interval_plus_grace_period() -> None:
    """REQ-0003: the watchdog timeout is 2x the heartbeat interval plus the grace period."""
    services = HandlerServices(
        registry=ChargePointRegistryStore(),
        connectors=ConnectorStateStore(),
        transactions=TransactionManager(),
        meter_values=MeterValueStore(),
        authorization=StaticAuthorizationProvider.empty(),
        events=EventBus(),
        heartbeat_interval_seconds=100,
        heartbeat_grace_period_seconds=3.0,
    )
    assert services.heartbeat_timeout_seconds == 203.0


def test_extract_meter_samples_uses_the_default_measurand_when_absent() -> None:
    """A `sampled_value` entry without `measurand` falls back to `Energy.Active.Import.Register`."""
    samples = _extract_meter_samples([{"timestamp": "2026-08-21T10:00:00Z", "sampled_value": [{"value": "42"}]}])
    assert len(samples) == 1
    assert samples[0].measurand == "Energy.Active.Import.Register"
    assert samples[0].value == "42"


def test_extract_meter_samples_parses_all_fields() -> None:
    """A fully-populated `sampled_value` entry maps every field onto `MeterSample`."""
    samples = _extract_meter_samples(
        [
            {
                "timestamp": "2026-08-21T10:00:00Z",
                "sampled_value": [
                    {"value": "230", "measurand": "Voltage", "unit": "V", "context": "Sample.Periodic", "phase": "L1"}
                ],
            }
        ]
    )
    assert samples[0].measurand == "Voltage"
    assert samples[0].unit == "V"
    assert samples[0].context == "Sample.Periodic"
    assert samples[0].phase == "L1"


# -- Charge-point-initiated handlers ------------------------------------------


async def test_on_boot_notification_records_the_boot_and_accepts() -> None:
    """BootNotification.req records vendor/model/firmware and always accepts."""
    handler, services, _connection = _build_handler()
    events: list[StateChangeEvent] = []
    services.events.subscribe(events.append)

    response = await handler.on_boot_notification(
        charge_point_vendor="Acme", charge_point_model="Charger-1", firmware_version="1.2.3"
    )

    assert response.status == ocpp_enums.RegistrationStatus.accepted
    assert response.interval == 300
    snapshot = services.registry.get(CHARGE_POINT_ID)
    assert snapshot.vendor == "Acme"
    assert snapshot.model == "Charger-1"
    assert snapshot.firmware_version == "1.2.3"
    assert events == [StateChangeEvent(CHARGE_POINT_ID, None, None)]


async def test_on_heartbeat_records_and_echoes_server_time() -> None:
    """Heartbeat.req updates the last-heartbeat timestamp and returns the current server time."""
    handler, services, _connection = _build_handler()

    response = await handler.on_heartbeat()

    assert response.current_time.endswith("Z")
    assert services.registry.get(CHARGE_POINT_ID) is not None


async def test_on_status_notification_updates_connector_state() -> None:
    """StatusNotification.req writes the connector's status/error code."""
    handler, services, _connection = _build_handler()

    await handler.on_status_notification(connector_id=1, error_code="NoError", status="Available")

    snapshot = services.connectors.get(CHARGE_POINT_ID, 1)
    assert snapshot.status == "Available"
    assert snapshot.error_code == "NoError"


async def test_on_authorize_returns_the_provider_decision() -> None:
    """Authorize.req reflects the configured authorization provider's decision."""
    handler, _services, _connection = _build_handler(StaticAuthorizationProvider([StaticIdTagEntry(id_tag="TAG1")]))

    accepted = await handler.on_authorize(id_tag="TAG1")
    rejected = await handler.on_authorize(id_tag="UNKNOWN")

    assert accepted.id_tag_info.status == ocpp_enums.AuthorizationStatus.accepted
    assert rejected.id_tag_info.status == ocpp_enums.AuthorizationStatus.invalid


async def test_on_start_transaction_opens_a_transaction_and_rounds_the_meter_value() -> None:
    """StartTransaction.req opens a transaction and rounds a non-integer meterStart (ADR-0005)."""
    handler, services, _connection = _build_handler(StaticAuthorizationProvider([StaticIdTagEntry(id_tag="TAG1")]))

    response = await handler.on_start_transaction(
        connector_id=1, id_tag="TAG1", meter_start=1000.4, timestamp="2026-08-21T10:00:00Z"
    )

    assert response.id_tag_info.status == ocpp_enums.AuthorizationStatus.accepted
    transaction = services.transactions.get(response.transaction_id)
    assert transaction.meter_start_wh == 1000  # rounded
    assert transaction.connector_id == 1


async def test_on_stop_transaction_closes_and_records_meter_values() -> None:
    """StopTransaction.req closes the transaction, rounds meterStop, and records `transactionData`."""
    handler, services, _connection = _build_handler()
    started = await handler.on_start_transaction(
        connector_id=1, id_tag="TAG1", meter_start=0, timestamp="2026-08-21T10:00:00Z"
    )

    response = await handler.on_stop_transaction(
        meter_stop=1500.6,
        timestamp="2026-08-21T10:30:00Z",
        transaction_id=started.transaction_id,
        reason="Local",
        transaction_data=[
            {
                "timestamp": "2026-08-21T10:30:00Z",
                "sampled_value": [{"value": "1500", "measurand": "Energy.Active.Import.Register"}],
            }
        ],
    )

    assert response.id_tag_info is None
    transaction = services.transactions.get(started.transaction_id)
    assert transaction.meter_stop_wh == 1501  # rounded
    assert transaction.stop_reason == "Local"
    recorded = services.meter_values.get_for_transaction(started.transaction_id)
    assert len(recorded) == 1


async def test_on_stop_transaction_with_id_tag_returns_its_authorization() -> None:
    """An optional `idTag` on StopTransaction.req gets its own authorization decision back."""
    handler, _services, _connection = _build_handler(StaticAuthorizationProvider([StaticIdTagEntry(id_tag="TAG1")]))
    started = await handler.on_start_transaction(
        connector_id=1, id_tag="TAG1", meter_start=0, timestamp="2026-08-21T10:00:00Z"
    )

    response = await handler.on_stop_transaction(
        meter_stop=100, timestamp="2026-08-21T10:05:00Z", transaction_id=started.transaction_id, id_tag="TAG1"
    )

    assert response.id_tag_info.status == ocpp_enums.AuthorizationStatus.accepted


async def test_on_stop_transaction_with_unknown_transaction_id_does_not_raise() -> None:
    """An unknown `transactionId` (REQ-0007 AC3) is a valid CallResult, not an error."""
    handler, _services, _connection = _build_handler()

    response = await handler.on_stop_transaction(meter_stop=100, timestamp="2026-08-21T10:00:00Z", transaction_id=999)

    assert response.id_tag_info is None


async def test_on_meter_values_records_samples_and_publishes() -> None:
    """MeterValues.req records every reported sample against the connector/transaction."""
    handler, services, _connection = _build_handler()
    events: list[StateChangeEvent] = []
    services.events.subscribe(events.append)

    await handler.on_meter_values(
        connector_id=1,
        meter_value=[
            {
                "timestamp": "2026-08-21T10:00:00Z",
                "sampled_value": [{"value": "5000", "measurand": "Power.Active.Import"}],
            }
        ],
        transaction_id=42,
    )

    recorded = services.meter_values.get_for_connector(CHARGE_POINT_ID, 1)
    assert len(recorded) == 1
    assert recorded[0].measurand == "Power.Active.Import"
    assert events == [StateChangeEvent(CHARGE_POINT_ID, 1, 42)]


# -- Central-System-initiated outbound calls (self.call patched) -------------


async def test_remote_start_transaction_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.RemoteStartTransaction(status="Accepted"))

    assert await handler.remote_start_transaction(1, "TAG1") == "Accepted"


async def test_remote_stop_transaction_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.RemoteStopTransaction(status="Rejected"))

    assert await handler.remote_stop_transaction(42) == "Rejected"


async def test_reset_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.Reset(status="Accepted"))

    assert await handler.reset("Soft") == "Accepted"


async def test_unlock_connector_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.UnlockConnector(status="Unlocked"))

    assert await handler.unlock_connector(1) == "Unlocked"


async def test_get_configuration_returns_known_and_unknown_keys() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(
        return_value=ocpp_call_result.GetConfiguration(
            configuration_key=[{"key": "HeartbeatInterval", "value": "300", "readonly": False}],
            unknown_key=["NotAKey"],
        )
    )

    known, unknown = await handler.get_configuration(["HeartbeatInterval", "NotAKey"])

    assert known == [{"key": "HeartbeatInterval", "value": "300", "readonly": False}]
    assert unknown == ["NotAKey"]


async def test_get_configuration_defaults_missing_lists_to_empty() -> None:
    """python-ocpp allows `None` for both list fields -- treat that as empty, not a crash."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.GetConfiguration(configuration_key=None, unknown_key=None))

    known, unknown = await handler.get_configuration(None)

    assert known == []
    assert unknown == []


async def test_change_configuration_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.ChangeConfiguration(status="RebootRequired"))

    assert await handler.change_configuration("Key", "Value") == "RebootRequired"


async def test_set_charging_profile_without_phases() -> None:
    """No `number_phases` means no `numberPhases` sent in the charging schedule period."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.SetChargingProfile(status="Accepted"))

    status = await handler.set_charging_profile(1, 100, 5000.0)

    assert status == "Accepted"
    sent_profile = handler.call.call_args.args[0].cs_charging_profiles
    period = sent_profile.charging_schedule.charging_schedule_period[0]
    assert period.limit == 5000.0
    assert period.number_phases is None


async def test_set_charging_profile_with_phases() -> None:
    """An explicit `number_phases` is passed through to the charging schedule period."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.SetChargingProfile(status="Accepted"))

    await handler.set_charging_profile(1, 100, 7400.0, number_phases=3)

    sent_profile = handler.call.call_args.args[0].cs_charging_profiles
    period = sent_profile.charging_schedule.charging_schedule_period[0]
    assert period.number_phases == 3


async def test_clear_charging_profile_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.ClearChargingProfile(status="Accepted"))

    assert await handler.clear_charging_profile(1) == "Accepted"


async def test_get_composite_schedule_with_no_schedule() -> None:
    """A `None` `chargingSchedule` (e.g. no active profile) still returns a valid, empty result."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(
        return_value=ocpp_call_result.GetCompositeSchedule(
            status="Accepted", connector_id=1, schedule_start=None, charging_schedule=None
        )
    )

    result = await handler.get_composite_schedule(1, 60)

    assert result.status == "Accepted"
    assert result.connector_id == 1
    assert result.periods == ()


async def test_get_composite_schedule_discards_periods_on_unit_mismatch() -> None:
    """A charge point answering in Amperes instead of the requested Watts gets no fabricated periods.

    `charging_schedule`'s keys are already snake_case here, matching what python-ocpp's own `call()`
    delivers in production (it snake_cases the whole response, including nested dicts, before
    constructing the `call_result` dataclass) -- mocking `handler.call` directly bypasses that step,
    so the mocked payload has to already be in that shape.
    """
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(
        return_value=ocpp_call_result.GetCompositeSchedule(
            status="Accepted",
            connector_id=1,
            schedule_start="2026-08-21T10:00:00Z",
            charging_schedule={
                "charging_rate_unit": "A",
                "duration": 3600,
                "charging_schedule_period": [{"start_period": 0, "limit": 16}],
            },
        )
    )

    result = await handler.get_composite_schedule(1, 3600)

    assert result.periods == ()
    assert result.charging_rate_unit == "A"
    assert result.duration_seconds == 3600


async def test_get_composite_schedule_parses_periods_when_units_match() -> None:
    """A matching `W` schedule is parsed into `ChargingSchedulePeriodInfo` entries."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(
        return_value=ocpp_call_result.GetCompositeSchedule(
            status="Accepted",
            connector_id=1,
            schedule_start="2026-08-21T10:00:00Z",
            charging_schedule={
                "charging_rate_unit": "W",
                "duration": 3600,
                "charging_schedule_period": [{"start_period": 0, "limit": 7400.0}],
            },
        )
    )

    result = await handler.get_composite_schedule(1, 3600)

    assert len(result.periods) == 1
    assert result.periods[0].start_offset_seconds == 0
    assert result.periods[0].limit_watts == 7400.0


async def test_change_availability_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.ChangeAvailability(status="Scheduled"))

    assert await handler.change_availability(1, "Inoperative") == "Scheduled"


async def test_trigger_message_returns_the_status() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.TriggerMessage(status="NotImplemented"))

    assert await handler.trigger_message("StatusNotification", 1) == "NotImplemented"


async def test_get_diagnostics_returns_the_file_name() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.GetDiagnostics(file_name="diag.zip"))

    result = await handler.get_diagnostics(
        "ftp://example/", retries=None, retry_interval=None, start_time=None, stop_time=None
    )

    assert result == "diag.zip"


async def test_get_diagnostics_returns_none_when_the_charge_point_reports_none() -> None:
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=ocpp_call_result.GetDiagnostics(file_name=None))

    result = await handler.get_diagnostics(
        "ftp://example/", retries=None, retry_interval=None, start_time=None, stop_time=None
    )

    assert result is None


async def test_a_rejected_call_result_raises_via_expect_response() -> None:
    """`self.call(..., suppress=True)` returns `None` for a CallError -- that must surface, not vanish."""
    handler, _services, _connection = _build_handler()
    handler.call = AsyncMock(return_value=None)

    with pytest.raises(ChargePointCallRejectedError):
        await handler.reset("Soft")


# -- Connection lifecycle / plumbing ------------------------------------------


def test_charge_point_id_property_returns_the_underlying_id() -> None:
    handler, _services, _connection = _build_handler()
    assert handler.charge_point_id == CHARGE_POINT_ID


async def test_close_connection_closes_the_underlying_websocket() -> None:
    handler, _services, connection = _build_handler()

    await handler.close_connection(reason="replaced by new connection")

    connection.close.assert_awaited_once_with(reason="replaced by new connection")


async def test_route_message_notifies_the_watchdog_and_dispatches_to_a_handler() -> None:
    """A raw inbound message notifies the watchdog and reaches the matching `on_*` handler."""
    handler, services, connection = _build_handler()
    notified = []
    handler.attach_watchdog_notifier(lambda: notified.append(True))
    raw_heartbeat = '[2,"1","Heartbeat",{}]'

    await handler.route_message(raw_heartbeat)

    assert notified == [True]
    connection.send.assert_awaited_once()
    assert services.registry.get(CHARGE_POINT_ID) is not None
