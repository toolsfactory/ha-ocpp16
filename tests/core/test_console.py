"""Tests for `core/console.py` (REQ-0032/REQ-0033 interactive console).

`_dispatch`/`_cmd_*` take a plain `app: CentralSystemApp` and need no TTY -- driven directly against
a real `CentralSystemApp` with a registered fake connection (`mock_charge_point_connection`, same
fixture `tests/conftest.py` already provides for the HA-layer tests). Only `run_console()`'s loop
touches `PromptSession`; that's driven via `prompt_toolkit`'s own testing utilities
(`create_pipe_input`/`create_app_session`) instead of a real terminal.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

from prompt_toolkit.application import create_app_session
from prompt_toolkit.input import create_pipe_input
from prompt_toolkit.output import DummyOutput
import pytest

from custom_components.ocpp16.core.app import CentralSystemApp
from custom_components.ocpp16.core.config import AppConfig
from custom_components.ocpp16.core.console import _dispatch, _help_text, run_console
from custom_components.ocpp16.core.domain.commands import CompositeScheduleResult

CHARGE_POINT_ID = "CP001"


def _build_app(connection: AsyncMock) -> CentralSystemApp:
    app = CentralSystemApp(AppConfig())
    app.registry.register_connection(CHARGE_POINT_ID, connection)
    return app


# -- _dispatch: parsing/routing/error handling --------------------------------


async def test_dispatch_ignores_a_blank_line(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "   ") == ""


async def test_dispatch_reports_an_unknown_command(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, "flibbertigibbet")
    assert "Unbekanntes Kommando" in output
    assert _help_text() in output


async def test_dispatch_reports_invalid_shell_quoting(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, 'start "unterminated')
    assert "Ungültige Eingabe" in output


async def test_dispatch_is_case_insensitive_for_the_command_name(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "HELP") == _help_text()


async def test_dispatch_surfaces_a_command_error(mock_charge_point_connection: AsyncMock) -> None:
    """`ChargePointNotConnectedError` (a `CommandError`) becomes a readable message, not a crash."""
    app = CentralSystemApp(AppConfig())  # no connection registered

    output = await _dispatch(app, "reset CP001 Soft")

    assert "Fehler:" in output


async def test_dispatch_reports_an_invalid_argument(mock_charge_point_connection: AsyncMock) -> None:
    """A non-integer where an int is expected is `Ungültiges Argument`, not a stack trace."""
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, "stop not-a-number")
    assert "Ungültiges Argument" in output


async def test_dispatch_catches_unexpected_exceptions(
    mock_charge_point_connection: AsyncMock, caplog: pytest.LogCaptureFixture
) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.reset.side_effect = RuntimeError("boom")

    output = await _dispatch(app, "reset CP001 Soft")

    assert output == "Unerwarteter Fehler — siehe Log für Details."
    assert "Unbehandelter Fehler" in caplog.text


# -- status ---------------------------------------------------------------


async def test_status_with_no_charge_points(mock_charge_point_connection: AsyncMock) -> None:
    app = CentralSystemApp(AppConfig())
    assert await _dispatch(app, "status") == "Keine Charge Points verbunden."


async def test_status_lists_charge_points_connectors_and_active_transactions(
    mock_charge_point_connection: AsyncMock,
) -> None:
    app = _build_app(mock_charge_point_connection)
    app.registry.mark_boot(
        CHARGE_POINT_ID, vendor="Acme", model="X1", firmware_version="1.0", boot_at=datetime.now(UTC)
    )
    app.connectors.update(CHARGE_POINT_ID, 1, status="Available", error_code=None)
    app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID,
        connector_id=1,
        id_tag="TAG1",
        meter_start_wh=0,
        started_at=datetime.now(UTC),
    )

    output = await _dispatch(app, "status")

    assert "CP001" in output
    assert "vendor=Acme" in output
    assert "connector 1: Available" in output
    assert "idTag=TAG1" in output


# -- start/stop -------------------------------------------------------------


async def test_start_with_a_specific_connector(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "start CP001 1 TAG1") == "Ladevorgang gestartet."
    mock_charge_point_connection.remote_start_transaction.assert_awaited_once_with(1, "TAG1")


async def test_start_with_no_specific_connector_uses_a_dash(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    await _dispatch(app, "start CP001 - TAG1")
    mock_charge_point_connection.remote_start_transaction.assert_awaited_once_with(None, "TAG1")


async def test_start_reports_a_rejection(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.remote_start_transaction.return_value = "Rejected"

    assert await _dispatch(app, "start CP001 1 TAG1") == "Charge Point hat abgelehnt (Rejected)."


async def test_start_reports_wrong_argument_count(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert "Usage: start" in await _dispatch(app, "start CP001")


async def test_stop_reports_success_and_rejection(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    transaction = app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID, connector_id=1, id_tag="TAG1", meter_start_wh=0, started_at=datetime.now(UTC)
    )

    assert await _dispatch(app, f"stop {transaction.transaction_id}") == "Ladevorgang gestoppt."

    mock_charge_point_connection.remote_stop_transaction.return_value = "Rejected"
    transaction2 = app.transactions.start_transaction(
        charge_point_id=CHARGE_POINT_ID, connector_id=1, id_tag="TAG1", meter_start_wh=0, started_at=datetime.now(UTC)
    )
    assert await _dispatch(app, f"stop {transaction2.transaction_id}") == "Charge Point hat abgelehnt (Rejected)."


# -- reset/unlock ------------------------------------------------------------


async def test_reset_rejects_an_invalid_reset_type(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, "reset CP001 Medium")
    assert "Soft" in output and "Hard" in output


async def test_reset_reports_success(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "reset CP001 Soft") == "Reset akzeptiert."


async def test_unlock_reports_the_status(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "unlock CP001 1") == "Ergebnis: Unlocked"


# -- getconfig/setconfig ------------------------------------------------------


async def test_getconfig_requires_a_charge_point_id(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert "Usage: getconfig" in await _dispatch(app, "getconfig")


async def test_getconfig_formats_entries_and_unknown_keys(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.get_configuration.return_value = (
        [{"key": "HeartbeatInterval", "value": "300", "readonly": False}],
        ["NotAKey"],
    )

    output = await _dispatch(app, "getconfig CP001 HeartbeatInterval NotAKey")

    assert "HeartbeatInterval = 300 (readonly=False)" in output
    assert "unbekannte Schlüssel: NotAKey" in output


async def test_getconfig_reports_nothing_gemeldet_when_empty(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.get_configuration.return_value = ([], [])

    assert await _dispatch(app, "getconfig CP001") == "Keine Konfigurationswerte gemeldet."


async def test_setconfig_flags_a_required_reboot(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.change_configuration.return_value = "RebootRequired"

    output = await _dispatch(app, "setconfig CP001 Key Value")

    assert "erst nach einem Neustart" in output


async def test_setconfig_reports_the_status_otherwise(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "setconfig CP001 Key Value") == "Ergebnis: Accepted"


# -- setlimit/clearlimit/getlimit --------------------------------------------


async def test_setlimit_requires_three_to_four_args(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert "Usage: setlimit" in await _dispatch(app, "setlimit CP001")
    assert "Usage: setlimit" in await _dispatch(app, "setlimit CP001 1 5000 3 extra")


async def test_setlimit_without_number_phases(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, "setlimit CP001 1 5000")
    assert "Ergebnis: Accepted" in output
    mock_charge_point_connection.set_charging_profile.assert_awaited_once_with(1, 1, 5000.0, None)


async def test_setlimit_with_number_phases(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    await _dispatch(app, "setlimit CP001 1 7400 3")
    mock_charge_point_connection.set_charging_profile.assert_awaited_once_with(1, 1, 7400.0, 3)


async def test_clearlimit_reports_the_status(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert await _dispatch(app, "clearlimit CP001 1") == "Ergebnis: Accepted"


async def test_getlimit_requires_two_to_three_args(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    assert "Usage: getlimit" in await _dispatch(app, "getlimit CP001")


async def test_getlimit_reports_a_non_accepted_status(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.get_composite_schedule.return_value = CompositeScheduleResult(status="Rejected")

    assert await _dispatch(app, "getlimit CP001 1") == "Ergebnis: Rejected"


async def test_getlimit_reports_accepted_with_no_periods(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    mock_charge_point_connection.get_composite_schedule.return_value = CompositeScheduleResult(status="Accepted")

    output = await _dispatch(app, "getlimit CP001 1")

    assert output == "Ergebnis: Accepted (keine Zeitplan-Info gemeldet)"


async def test_getlimit_formats_periods_when_present(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    # mock_charge_point_connection's default get_composite_schedule already returns one period.
    output = await _dispatch(app, "getlimit CP001 1 1800")
    assert "Ergebnis: Accepted" in output
    assert "ab +0s:" in output


# -- help ---------------------------------------------------------------


async def test_help_lists_every_command(mock_charge_point_connection: AsyncMock) -> None:
    app = _build_app(mock_charge_point_connection)
    output = await _dispatch(app, "help")
    for command in ("status", "start", "stop", "reset", "unlock", "getconfig", "setconfig", "setlimit", "getlimit"):
        assert command in output


# -- run_console: the PromptSession loop itself -------------------------------


async def test_run_console_processes_a_command_and_exits_cleanly_on_eof(
    mock_charge_point_connection: AsyncMock, capsys: pytest.CaptureFixture[str]
) -> None:
    """The loop reads a line, dispatches it, prints the result, then exits on EOF without raising."""
    app = _build_app(mock_charge_point_connection)

    with create_pipe_input() as pipe_input, create_app_session(input=pipe_input, output=DummyOutput()):
        pipe_input.send_text("help\n")
        pipe_input.close()
        await run_console(app)  # must not raise

    out = capsys.readouterr().out
    assert "interaktive Konsole" in out


async def test_run_console_ignores_blank_lines(
    mock_charge_point_connection: AsyncMock, capsys: pytest.CaptureFixture[str]
) -> None:
    app = _build_app(mock_charge_point_connection)

    with create_pipe_input() as pipe_input, create_app_session(input=pipe_input, output=DummyOutput()):
        pipe_input.send_text("   \n")
        pipe_input.close()
        await run_console(app)  # must not raise on a blank line before EOF
