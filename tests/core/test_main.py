"""Tests for `core/__main__.py`, the standalone-core entry point."""

from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.ocpp16.core.__main__ import main
from custom_components.ocpp16.core.config import AppConfig

_MODULE = "custom_components.ocpp16.core.__main__"


def test_main_builds_and_runs_the_app_from_parsed_args() -> None:
    """`main()` parses argv, configures logging, and runs the app until `asyncio.run` returns.

    Deliberately does not mock `asyncio.run` itself: mocking it would leave the coroutine
    `app.run()` creates unawaited (never passed to a real event loop), which pytest flags as an
    unraisable exception at some later, unrelated point once the coroutine gets garbage collected.
    Letting the real `asyncio.run` drive the `AsyncMock` coroutine avoids that entirely.
    """
    with (
        patch(f"{_MODULE}.parse_args", return_value=AppConfig(host="1.2.3.4")) as mock_parse_args,
        patch(f"{_MODULE}.configure_logging") as mock_configure_logging,
        patch(f"{_MODULE}.CentralSystemApp") as mock_app_cls,
    ):
        mock_app_cls.return_value.run = AsyncMock()
        main(["--host", "1.2.3.4"])

    mock_parse_args.assert_called_once_with(["--host", "1.2.3.4"])
    mock_configure_logging.assert_called_once_with(AppConfig(host="1.2.3.4").log_level)
    mock_app_cls.assert_called_once_with(AppConfig(host="1.2.3.4"))
    mock_app_cls.return_value.run.assert_awaited_once()


def test_main_swallows_keyboard_interrupt() -> None:
    """A `KeyboardInterrupt` from `asyncio.run` (Ctrl+C) exits cleanly instead of a stack trace."""
    with (
        patch(f"{_MODULE}.parse_args", return_value=AppConfig()),
        patch(f"{_MODULE}.configure_logging"),
        patch(f"{_MODULE}.CentralSystemApp", return_value=MagicMock()),
        patch(f"{_MODULE}.asyncio.run", side_effect=KeyboardInterrupt),
    ):
        main([])  # must not raise
