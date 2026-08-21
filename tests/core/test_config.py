"""Tests for `core/config.py`'s standalone-CLI argument parsing."""

import argparse
import logging
from pathlib import Path

import pytest

from custom_components.ocpp.core.config import AppConfig, _parse_log_level, parse_args


def test_parse_args_defaults() -> None:
    """No arguments produces the same defaults as a bare `AppConfig()`."""
    config = parse_args([])
    assert config == AppConfig()


def test_parse_args_all_flags() -> None:
    """Every CLI flag maps to the matching `AppConfig` field, including the Phase-5 TLS pair."""
    config = parse_args(
        [
            "--host",
            "192.168.1.1",
            "--port",
            "9500",
            "--log-level",
            "DEBUG",
            "--heartbeat-interval",
            "60",
            "--heartbeat-grace-period",
            "2.5",
            "--authorization-file",
            "/etc/ocpp/auth.json",
            "--certificate-file",
            "/etc/ocpp/cert.pem",
            "--private-key-file",
            "/etc/ocpp/key.pem",
        ]
    )
    assert config == AppConfig(
        host="192.168.1.1",
        port=9500,
        log_level=logging.DEBUG,
        heartbeat_interval_seconds=60,
        heartbeat_grace_period_seconds=2.5,
        authorization_file=Path("/etc/ocpp/auth.json"),
        certificate_path=Path("/etc/ocpp/cert.pem"),
        private_key_path=Path("/etc/ocpp/key.pem"),
    )


@pytest.mark.parametrize("value", ["debug", "DEBUG", "Debug"])
def test_parse_log_level_is_case_insensitive(value: str) -> None:
    """`_parse_log_level` accepts any case, matching `logging.getLevelName`'s own behavior."""
    assert _parse_log_level(value) == logging.DEBUG


def test_parse_log_level_rejects_unknown_level() -> None:
    """An unknown level name raises `ArgumentTypeError`, which `argparse` turns into a usage error."""
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_log_level("NOT_A_LEVEL")


def test_parse_args_rejects_unknown_log_level(capsys: pytest.CaptureFixture[str]) -> None:
    """An invalid `--log-level` value exits with a usage error instead of crashing."""
    with pytest.raises(SystemExit):
        parse_args(["--log-level", "NOT_A_LEVEL"])
    assert "Unbekannter Log-Level" in capsys.readouterr().err


def test_heartbeat_timeout_seconds_is_twice_the_interval_plus_grace_period() -> None:
    """REQ-0003: the watchdog timeout is 2x the heartbeat interval plus the grace period."""
    config = AppConfig(heartbeat_interval_seconds=100, heartbeat_grace_period_seconds=3.0)
    assert config.heartbeat_timeout_seconds == 203.0
