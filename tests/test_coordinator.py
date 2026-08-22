"""Tests for `Ocpp16Coordinator`: it republishes `QueryService` events, nothing more.

Per the plan's "thin coordinator" decision, the coordinator holds only the last
event -- entities keep reading `QueryService` directly. These tests exercise
that hand-off, not entity behavior (covered in `tests/sensor/`/`tests/switch/`).
"""

from collections.abc import Callable

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.ocpp16.core.domain.models import StateChangeEvent
from homeassistant.core import HomeAssistant

CHARGE_POINT_ID = "CP001"


async def test_coordinator_data_updates_on_query_service_event(
    hass: HomeAssistant, init_integration: MockConfigEntry, publish_state_change: Callable[..., None]
) -> None:
    """A published `StateChangeEvent` becomes the coordinator's `.data`."""
    entry_data = init_integration.runtime_data
    assert entry_data.coordinator.data is None

    publish_state_change(entry_data.app, charge_point_id=CHARGE_POINT_ID, connector_id=1)
    await hass.async_block_till_done()

    assert entry_data.coordinator.data == StateChangeEvent(
        charge_point_id=CHARGE_POINT_ID, connector_id=1, transaction_id=None
    )


async def test_coordinator_unsubscribes_on_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry, publish_state_change: Callable[..., None]
) -> None:
    """After unload, further events no longer reach the (torn-down) coordinator."""
    entry_data = init_integration.runtime_data
    app = entry_data.app
    coordinator = entry_data.coordinator

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()

    publish_state_change(app, charge_point_id=CHARGE_POINT_ID, connector_id=1)
    await hass.async_block_till_done()

    assert coordinator.data is None
