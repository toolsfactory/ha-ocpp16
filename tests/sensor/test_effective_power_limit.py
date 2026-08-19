"""Tests for `OccpEffectivePowerLimitSensor` (Fähigkeit 5, REQ-0035 AC4)."""

import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.occp.const import DOMAIN
from custom_components.occp.core.domain.commands import CompositeScheduleResult
from custom_components.occp.entity_utils.device import connector_identifier
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

CHARGE_POINT_ID = "CP001"


async def test_refreshes_via_get_composite_schedule_on_a_connector_scoped_event(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """REQ-0035 AC4: `unknown` (not `0`) until the first successful GetCompositeSchedule."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_effective_power_limit_w",
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "unknown"

    # The entity subscribes to the coordinator only after being added, so the
    # creating event above never reaches its own _handle_coordinator_update --
    # a second, connector-scoped event is what a real SetChargingProfile
    # follow-up StatusNotification would look like.
    publish_state_change(entry_data.app, connector_id=1)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "5000.0"
    mock_charge_point_connection.get_composite_schedule.assert_awaited_with(1, 3600)


async def test_coalesces_a_burst_of_events_into_at_most_one_follow_up_call(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Three events while a `GetCompositeSchedule` call is in flight must not fire three calls.

    Regression test: `_handle_coordinator_update` used to start a new background
    task per qualifying event with no in-flight check, so a burst of events (e.g.
    several `MeterValues` in a row) could fire several concurrent OCPP round trips
    for the same connector. Now at most one call is ever in flight, and any events
    that arrive while it is running coalesce into exactly one follow-up call.
    """
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()

    gate = asyncio.Event()

    async def _gated_get_composite_schedule(*_args, **_kwargs):
        await gate.wait()
        return mock_charge_point_connection.get_composite_schedule.return_value

    mock_charge_point_connection.get_composite_schedule.side_effect = _gated_get_composite_schedule

    # Fire the first event and let its background task actually start and block
    # on the gate, without draining the event loop fully (that would hang, since
    # the task cannot finish yet).
    publish_state_change(entry_data.app, connector_id=1)
    for _ in range(3):
        await asyncio.sleep(0)

    # Two more events arrive while the first call is still in flight.
    publish_state_change(entry_data.app, connector_id=1)
    publish_state_change(entry_data.app, connector_id=1)
    for _ in range(3):
        await asyncio.sleep(0)

    assert mock_charge_point_connection.get_composite_schedule.call_count == 1

    gate.set()
    await hass.async_block_till_done()

    # Coalesced: the burst produced exactly one follow-up call, not one per event.
    assert mock_charge_point_connection.get_composite_schedule.call_count == 2

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_effective_power_limit_w",
    )
    assert hass.states.get(entity_id).state == "5000.0"


async def test_ignores_events_for_a_different_connector(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A `GetCompositeSchedule` call would be wasted Central-System-initiated traffic for another connector."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection, connector_ids=(1, 2))
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    mock_charge_point_connection.get_composite_schedule.reset_mock()

    # Connector 2's own sensor legitimately refreshes on this event -- what
    # this test checks is that connector 1's sensor does not.
    publish_state_change(entry_data.app, connector_id=2)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_effective_power_limit_w",
    )
    assert hass.states.get(entity_id).state == "unknown"
    mock_charge_point_connection.get_composite_schedule.assert_awaited_once_with(2, 3600)


async def test_ignores_events_for_a_different_charge_point_with_the_same_connector_number(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """Two charge points on one instance, both with a connector 1, must not cross-trigger."""
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection, charge_point_id=CHARGE_POINT_ID)
    other_connection = AsyncMock()
    boot_charge_point(entry_data.app, other_connection, charge_point_id="CP999")
    publish_state_change(entry_data.app, charge_point_id=CHARGE_POINT_ID, connector_id=None)
    publish_state_change(entry_data.app, charge_point_id="CP999", connector_id=None)
    await hass.async_block_till_done()
    mock_charge_point_connection.get_composite_schedule.reset_mock()

    # A charge-point-wide event (connector_id=None) for the OTHER charge point
    # must not refresh CHARGE_POINT_ID's connector 1 sensor.
    publish_state_change(entry_data.app, charge_point_id="CP999", connector_id=None)
    await hass.async_block_till_done()

    mock_charge_point_connection.get_composite_schedule.assert_not_awaited()


async def test_stays_unknown_when_the_charge_point_ignores_the_requested_unit(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_charge_point_connection,
    boot_charge_point: Callable[..., None],
    publish_state_change: Callable[..., None],
) -> None:
    """A response in a unit other than the requested W is unusable, not silently mislabeled as watts.

    `core/ocpp16/handlers.py`'s `get_composite_schedule` drops the periods in this
    case (see its ADR-0006 comment) rather than propagate a wrongly-labeled
    number -- this mirrors that outcome (`status="Accepted"`, `periods=()`) at
    the connection boundary, the same shape `get_effective_power_limit_w`
    would actually see.
    """
    entry_data = init_integration.runtime_data
    boot_charge_point(entry_data.app, mock_charge_point_connection)
    mock_charge_point_connection.get_composite_schedule.return_value = CompositeScheduleResult(
        status="Accepted", charging_rate_unit="A", periods=()
    )
    publish_state_change(entry_data.app, connector_id=None)
    await hass.async_block_till_done()
    publish_state_change(entry_data.app, connector_id=1)
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor",
        DOMAIN,
        f"{connector_identifier(init_integration.entry_id, CHARGE_POINT_ID, 1)}_effective_power_limit_w",
    )
    assert hass.states.get(entity_id).state == "unknown"
