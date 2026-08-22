"""Tests for `core/transport.py`'s WebSocket server (`start_server`/`_run_connection`).

Real localhost sockets, not mocks: `mock_app_start_stop` (used everywhere else in this suite)
patches `CentralSystemApp.start` wholesale, so nothing else in the suite ever calls `start_server()`
for real. These tests bind to `127.0.0.1:0` (an OS-assigned ephemeral port) and drive a real
`websockets` client through a full `BootNotification` round trip -- for the TLS test, this is also
the live `wss://` handshake verification (self-signed cert from the `tls_cert_pair` fixture,
client-side verification disabled the same way any test client talking to a self-signed cert
would need to).
"""

import asyncio
from pathlib import Path
import ssl

import pytest
import pytest_socket
import websockets
from websockets.asyncio.client import connect
from websockets.asyncio.server import Server

from custom_components.ocpp16.core.config import AppConfig
from custom_components.ocpp16.core.domain.authorization import StaticAuthorizationProvider
from custom_components.ocpp16.core.domain.connector_state import ConnectorStateStore
from custom_components.ocpp16.core.domain.events import EventBus
from custom_components.ocpp16.core.domain.meter_values import MeterValueStore
from custom_components.ocpp16.core.domain.registry import ChargePointRegistryStore
from custom_components.ocpp16.core.domain.transactions import TransactionManager
from custom_components.ocpp16.core.ocpp16.handlers import HandlerServices
from custom_components.ocpp16.core.transport import build_ssl_context, start_server

CHARGE_POINT_ID = "CP001"
_BOOT_NOTIFICATION = '[2,"1","BootNotification",{"chargePointVendor":"Test-Vendor","chargePointModel":"Test-Model"}]'


@pytest.fixture(autouse=True)
def _real_sockets() -> None:
    """Re-enable real sockets for this module.

    `pytest_homeassistant_custom_component`'s own `pytest_runtest_setup` hook unconditionally
    calls `pytest_socket.disable_socket()` on every test (not marker-aware), which runs after
    `pytest.mark.enable_socket` would have re-enabled them -- so the marker alone doesn't stick.
    Calling `enable_socket()` here, from a fixture body (which always runs after every
    `pytest_runtest_setup` hook has already fired), does.
    """
    pytest_socket.enable_socket()


def _build_services(
    *, heartbeat_interval_seconds: int = 300, heartbeat_grace_period_seconds: float = 5.0
) -> HandlerServices:
    return HandlerServices(
        registry=ChargePointRegistryStore(),
        connectors=ConnectorStateStore(),
        transactions=TransactionManager(),
        meter_values=MeterValueStore(),
        authorization=StaticAuthorizationProvider.empty(),
        events=EventBus(),
        heartbeat_interval_seconds=heartbeat_interval_seconds,
        heartbeat_grace_period_seconds=heartbeat_grace_period_seconds,
    )


def _server_port(server: Server) -> int:
    return server.sockets[0].getsockname()[1]


def _insecure_client_ssl_context() -> ssl.SSLContext:
    """A client context that accepts the test's self-signed certificate, like curl -k would."""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context


@pytest.fixture
async def running_server():
    """Yield `(server, services)`, bound to an ephemeral `ws://127.0.0.1` port; closed on teardown."""
    services = _build_services()
    server = await start_server(AppConfig(host="127.0.0.1", port=0), services)
    try:
        yield server, services
    finally:
        server.close()
        await server.wait_closed()


async def test_boot_notification_round_trip_over_plain_ws(running_server) -> None:
    """A real client connects over `ws://`, completes BootNotification, and the registry reflects it."""
    server, services = running_server
    uri = f"ws://127.0.0.1:{_server_port(server)}/{CHARGE_POINT_ID}"

    async with connect(uri, subprotocols=["ocpp1.6"]) as client:
        await client.send(_BOOT_NOTIFICATION)
        response = await asyncio.wait_for(client.recv(), timeout=5)

    assert '"Accepted"' in response
    snapshot = services.registry.get(CHARGE_POINT_ID)
    assert snapshot is not None
    assert snapshot.vendor == "Test-Vendor"
    assert snapshot.model == "Test-Model"


async def test_boot_notification_round_trip_over_wss(tls_cert_pair: tuple[Path, Path]) -> None:
    """The same round trip over `wss://` (Phase 5), using a real self-signed certificate."""
    cert_path, key_path = tls_cert_pair
    services = _build_services()
    server = await start_server(
        AppConfig(host="127.0.0.1", port=0), services, ssl_context=build_ssl_context(cert_path, key_path)
    )
    try:
        uri = f"wss://127.0.0.1:{_server_port(server)}/{CHARGE_POINT_ID}"
        async with connect(uri, subprotocols=["ocpp1.6"], ssl=_insecure_client_ssl_context()) as client:
            await client.send(_BOOT_NOTIFICATION)
            response = await asyncio.wait_for(client.recv(), timeout=5)

        assert '"Accepted"' in response
        assert services.registry.get(CHARGE_POINT_ID) is not None
    finally:
        server.close()
        await server.wait_closed()


async def test_connection_without_a_charge_point_id_is_rejected(running_server) -> None:
    """A connection to the bare root path (no charge point identity) is closed, not accepted."""
    server, _services = running_server
    uri = f"ws://127.0.0.1:{_server_port(server)}/"

    async with connect(uri, subprotocols=["ocpp1.6"]) as client:
        with pytest.raises(websockets.ConnectionClosed):
            await asyncio.wait_for(client.recv(), timeout=5)
        assert client.close_code == 1008


async def test_a_second_connection_with_the_same_identity_replaces_the_first(running_server) -> None:
    """REQ-0001 AC4: a reconnecting identity closes the previous connection instead of coexisting."""
    server, services = running_server
    uri = f"ws://127.0.0.1:{_server_port(server)}/{CHARGE_POINT_ID}"

    async with connect(uri, subprotocols=["ocpp1.6"]) as first:
        await first.send(_BOOT_NOTIFICATION)
        await asyncio.wait_for(first.recv(), timeout=5)

        async with connect(uri, subprotocols=["ocpp1.6"]) as second:
            await second.send(_BOOT_NOTIFICATION)
            await asyncio.wait_for(second.recv(), timeout=5)

            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(first.recv(), timeout=5)

    assert services.registry.get(CHARGE_POINT_ID) is not None


async def test_a_silent_connection_is_closed_after_the_heartbeat_timeout() -> None:
    """No inbound message within the tolerance window (REQ-0003) closes the connection."""
    services = _build_services(heartbeat_interval_seconds=0, heartbeat_grace_period_seconds=0.2)
    server = await start_server(AppConfig(host="127.0.0.1", port=0), services)
    try:
        uri = f"ws://127.0.0.1:{_server_port(server)}/{CHARGE_POINT_ID}"
        async with connect(uri, subprotocols=["ocpp1.6"]) as client:
            with pytest.raises(websockets.ConnectionClosed):
                await asyncio.wait_for(client.recv(), timeout=5)
    finally:
        server.close()
        await server.wait_closed()
