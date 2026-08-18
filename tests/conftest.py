"""Shared fixtures for the occp tests."""

from collections.abc import Callable, Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import CONF_HOST, CONF_PORT, DOMAIN
from custom_components.occp.core.app import CentralSystemApp
from custom_components.occp.core.domain.commands import ChargingSchedulePeriodInfo, CompositeScheduleResult
from custom_components.occp.core.domain.models import MeterSample, StateChangeEvent
from homeassistant.core import HomeAssistant

CHARGE_POINT_ID = "CP001"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load custom integrations in every test."""


@pytest.fixture
def mock_app_start_stop() -> Generator[None]:
    """Patch `CentralSystemApp.start`/`stop` so setup never binds a real socket."""
    with (
        patch("custom_components.occp.core.app.CentralSystemApp.start", new_callable=AsyncMock),
        patch("custom_components.occp.core.app.CentralSystemApp.stop", new_callable=AsyncMock),
    ):
        yield


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a config entry for this integration."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="OCCP (0.0.0.0:9000)",
        unique_id="0.0.0.0:9000",
        data={CONF_HOST: "0.0.0.0", CONF_PORT: 9000},
    )


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_app_start_stop: None,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration from a config entry.

    Returns:
        The config entry, now loaded.

    """
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.fixture
def mock_charge_point_connection() -> AsyncMock:
    """Return an `AsyncMock` satisfying the `ChargePointConnection` protocol.

    Every OCPP call accepts by default; individual tests override a method's
    `return_value`/`side_effect` for the rejection paths.
    """
    connection = AsyncMock()
    connection.charge_point_id = CHARGE_POINT_ID
    connection.remote_start_transaction.return_value = "Accepted"
    connection.remote_stop_transaction.return_value = "Accepted"
    connection.reset.return_value = "Accepted"
    connection.unlock_connector.return_value = "Unlocked"
    connection.get_configuration.return_value = ([{"key": "HeartbeatInterval", "value": "300", "readonly": False}], [])
    connection.change_configuration.return_value = "Accepted"
    connection.set_charging_profile.return_value = "Accepted"
    connection.clear_charging_profile.return_value = "Accepted"
    connection.change_availability.return_value = "Accepted"
    connection.get_composite_schedule.return_value = CompositeScheduleResult(
        status="Accepted", periods=[ChargingSchedulePeriodInfo(start_offset_seconds=0, limit_watts=5000.0)]
    )
    return connection


@pytest.fixture
def boot_charge_point() -> Callable[..., None]:
    """Return a function that seeds the core's domain stores as if a charge point had just booted.

    Drives the same write-side APIs the OCPP-1.6 handlers use
    (`registry`/`connectors`, both public on `CentralSystemApp`) instead of a
    real WebSocket round trip -- there is no HTTP API client to mock here, so
    this plays the role `mock_api_client` plays for a REST-backed integration.
    """

    def _boot_charge_point(
        app: CentralSystemApp,
        connection: AsyncMock,
        *,
        charge_point_id: str = CHARGE_POINT_ID,
        connector_ids: tuple[int, ...] = (1,),
    ) -> None:
        app.registry.register_connection(charge_point_id, connection)
        app.registry.mark_boot(
            charge_point_id,
            vendor="Test-Vendor",
            model="Test-Model",
            firmware_version="1.0.0",
            boot_at=datetime.now(UTC),
        )
        app.connectors.update(charge_point_id, 0, status="Available", error_code=None)
        for connector_id in connector_ids:
            app.connectors.update(charge_point_id, connector_id, status="Available", error_code=None)

    return _boot_charge_point


@pytest.fixture
def record_meter_sample() -> Callable[..., None]:
    """Return a function that records one measurand sample, mirroring a MeterValues handler call."""

    def _record_meter_sample(
        app: CentralSystemApp,
        *,
        charge_point_id: str = CHARGE_POINT_ID,
        connector_id: int = 1,
        measurand: str,
        value: str,
        unit: str | None = None,
        transaction_id: int | None = None,
    ) -> None:
        app.meter_values.record(
            charge_point_id=charge_point_id,
            connector_id=connector_id,
            transaction_id=transaction_id,
            samples=[
                MeterSample(
                    measurand=measurand,
                    value=value,
                    unit=unit,
                    context="Sample.Periodic",
                    phase=None,
                    recorded_at=datetime.now(UTC),
                )
            ],
        )

    return _record_meter_sample


@pytest.fixture
def publish_state_change() -> Callable[..., None]:
    """Return a function that publishes a `StateChangeEvent`, the same notification an OCPP-1.6 handler would fire.

    Drives the coordinator, the sensor/switch managers, and __init__.py's device
    registration -- all three subscribe on `app.query_service`/the coordinator.
    """

    def _publish_state_change(
        app: CentralSystemApp,
        *,
        charge_point_id: str = CHARGE_POINT_ID,
        connector_id: int | None = None,
        transaction_id: int | None = None,
    ) -> None:
        app.events.publish(
            StateChangeEvent(charge_point_id=charge_point_id, connector_id=connector_id, transaction_id=transaction_id)
        )

    return _publish_state_change
