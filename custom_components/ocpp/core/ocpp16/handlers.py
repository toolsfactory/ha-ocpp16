"""OCPP-1.6-Nachrichtenhandler: einzige Stelle im Kern, die ``ocpp.v16`` direkt verwendet.

REQ-0001, REQ-0003-REQ-0010, REQ-0012-REQ-0015. ``ChargePointHandler`` erbt von ``ocpp.v16.ChargePoint`` (ADR-0001) und ruft
für jede fachliche Wirkung ausschließlich Domänenservices aus ``ocpp.domain``
auf — kein HA-Bezug, keine Vermischung wie beim Negativbeispiel lbbrhzn/ocpp
(siehe architecture.md).
"""

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
import functools
import inspect
import logging
from typing import TypeVar

from custom_components.ocpp.core.domain.authorization import AuthorizationDecision, AuthorizationProvider
from custom_components.ocpp.core.domain.commands import (
    ChargePointCallRejectedError,
    ChargingSchedulePeriodInfo,
    CompositeScheduleResult,
)
from custom_components.ocpp.core.domain.connector_state import ConnectorStateStore
from custom_components.ocpp.core.domain.events import EventBus
from custom_components.ocpp.core.domain.meter_values import MeterValueStore
from custom_components.ocpp.core.domain.models import MeterSample, StateChangeEvent
from custom_components.ocpp.core.domain.registry import ChargePointRegistryStore
from custom_components.ocpp.core.domain.transactions import TransactionManager
from ocpp.routing import on
from ocpp.v16 import (
    ChargePoint as OcppChargePoint,
    call as ocpp_call,
    call_result as ocpp_call_result,
    datatypes as ocpp_datatypes,
    enums as ocpp_enums,
)

logger = logging.getLogger(__name__)

_DEFAULT_MEASURAND = "Energy.Active.Import.Register"

_F = TypeVar("_F", bound=Callable[..., Awaitable[object]])
_R = TypeVar("_R")


def _expect_response(response: _R | None) -> _R:
    """Return `response`, raising if python-ocpp suppressed a CallError into `None`."""
    if response is None:
        raise ChargePointCallRejectedError("Charge Point hat den Aufruf mit einem CallError quittiert.")
    return response


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _to_iso(value: datetime) -> str:
    return value.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _mask_id_tag(id_tag: str) -> str:
    """Return `id_tag` masked for logging -- only the last 4 characters stay visible.

    idTags identifieren einen konkreten Fahrer/eine Karte -- auf INFO-Level
    (Standard-Sichtbarkeit, anders als das volle Frame-Logging auf DEBUG,
    das bewusst Opt-in bleibt) sollen sie nicht im Klartext in Logs landen.
    """
    if len(id_tag) <= 4:
        return "*" * len(id_tag)
    return f"{'*' * (len(id_tag) - 4)}{id_tag[-4:]}"


def _to_id_tag_info(decision: AuthorizationDecision) -> ocpp_datatypes.IdTagInfo:
    return ocpp_datatypes.IdTagInfo(
        status=ocpp_enums.AuthorizationStatus(decision.status.value),
        parent_id_tag=decision.parent_id_tag,
        expiry_date=_to_iso(decision.expiry_date) if decision.expiry_date else None,
    )


def _extract_meter_samples(meter_value: Sequence[dict]) -> list[MeterSample]:
    samples: list[MeterSample] = []
    for entry in meter_value:
        recorded_at = _parse_timestamp(entry["timestamp"])
        samples.extend(
            MeterSample(
                measurand=sampled.get("measurand", _DEFAULT_MEASURAND),
                value=str(sampled["value"]),
                unit=sampled.get("unit"),
                context=sampled.get("context"),
                phase=sampled.get("phase"),
                recorded_at=recorded_at,
            )
            for sampled in entry.get("sampled_value", [])
        )
    return samples


def _log_handler_errors(func: _F) -> _F:
    """Wrap `func` to log unhandled exceptions before re-raising.

    Protokolliert unbehandelte Ausnahmen mit Charge-Point-Kontext, bevor
    sie erneut geworfen werden (REQ-0031 AC4) — python-ocpp fängt sie danach
    selbst ab und erzeugt daraus regulär einen ``CallError``.
    """

    @functools.wraps(func)
    async def wrapper(self: ChargePointHandler, *args: object, **kwargs: object):
        try:
            result = func(self, *args, **kwargs)
            if inspect.isawaitable(result):
                result = await result
        except Exception:
            self.cp_logger.exception("Unbehandelter Fehler in Handler '%s'", func.__name__)
            raise
        else:
            return result

    return wrapper  # type: ignore[return-value]


@dataclass
class HandlerServices:
    """Domain services and heartbeat config a `ChargePointHandler` calls into."""

    registry: ChargePointRegistryStore
    connectors: ConnectorStateStore
    transactions: TransactionManager
    meter_values: MeterValueStore
    authorization: AuthorizationProvider
    events: EventBus
    heartbeat_interval_seconds: int
    heartbeat_grace_period_seconds: float

    @property
    def heartbeat_timeout_seconds(self) -> float:
        """Return the watchdog timeout derived from the heartbeat interval."""
        # Entscheidung REQ-0003: 2x vereinbartes Intervall + feste Grace-Period.
        return 2 * self.heartbeat_interval_seconds + self.heartbeat_grace_period_seconds


class ChargePointHandler(OcppChargePoint):
    """Central-System-seitige OCPP-1.6-Verbindung zu genau einem Charge Point."""

    def __init__(
        self,
        charge_point_id: str,
        connection: object,
        *,
        services: HandlerServices,
        cp_logger: logging.LoggerAdapter,
    ) -> None:
        """Initialize the connection with its domain services and loggers."""
        # Eigener, gedrosselter Logger für die Bibliotheks-internen
        # send/receive-Zeilen (immer INFO, siehe python-ocpp): REQ-0031
        # verlangt vollständige Rohnachrichten nur bei DEBUG, alles andere
        # (Verbindungs-/Transaktions-/Statusereignisse) bei INFO — das
        # übernehmen wir selbst über ``cp_logger`` bzw. ``route_message``/
        # ``_send`` unten. Der Logger-Name trägt die Charge-Point-Identität,
        # damit ein von der Bibliothek selbst protokollierter, unbehandelter
        # Fehler (z. B. Schema-Validierung, siehe REQ-0015) trotzdem
        # zuordenbar bleibt.
        wire_logger = logging.getLogger(f"ocpp.ocpp16.wire.{charge_point_id}")
        wire_logger.setLevel(logging.WARNING)
        super().__init__(charge_point_id, connection, logger=wire_logger)
        self._services = services
        self.cp_logger = cp_logger
        self._watchdog_notify: Callable[[], None] | None = None

    @property
    def charge_point_id(self) -> str:
        """Return the charge point's identity as used by python-ocpp."""
        return self.id

    def attach_watchdog_notifier(self, notify: Callable[[], None]) -> None:
        """Register `notify` to be called on every inbound message."""
        self._watchdog_notify = notify

    async def close_connection(self, *, reason: str = "") -> None:
        """Close the underlying WebSocket connection."""
        await self._connection.close(reason=reason)

    async def route_message(self, raw_msg: str) -> None:
        """Log the raw message, notify the watchdog, then dispatch as usual."""
        self.cp_logger.debug("RX: %s", raw_msg)
        if self._watchdog_notify is not None:
            self._watchdog_notify()
        await super().route_message(raw_msg)

    async def _send(self, message: str) -> None:
        self.cp_logger.debug("TX: %s", message)
        await super()._send(message)

    def _round_meter_value(self, value: int, *, field_name: str, action: str) -> int:
        """Round `value` to `int`, logging when the input was not already one.

        Rundet ``meterStart``/``meterStop`` kaufmännisch auf ``int``
        (ADR-0005, REQ-0006 AC4/REQ-0007 AC5) — die Schema-Validierung
        (``_compat.py``) akzeptiert dafür bereits Fließkommazahlen, die
        Domäne bleibt aber strikt ``int``-typisiert.
        """
        rounded = round(value)  # noqa: RUF057 -- annotated int, but real charge points send float (see docstring)
        if not isinstance(value, int):
            self.cp_logger.warning(
                "%s: %s=%s ist keine Ganzzahl, wird auf %s gerundet (ADR-0005)",
                action,
                field_name,
                value,
                rounded,
            )
        return rounded

    # -- Charge-Point-initiierte Nachrichten ---------------------------------

    @on(ocpp_enums.Action.boot_notification)
    @_log_handler_errors
    async def on_boot_notification(
        self,
        charge_point_vendor: str,
        charge_point_model: str,
        firmware_version: str | None = None,
        **kwargs: object,
    ) -> ocpp_call_result.BootNotification:
        """Handle BootNotification.req: record the boot and accept it."""
        boot_at = _utcnow()
        self._services.registry.mark_boot(
            self.id,
            vendor=charge_point_vendor,
            model=charge_point_model,
            firmware_version=firmware_version,
            boot_at=boot_at,
        )
        self.cp_logger.info(
            "BootNotification akzeptiert: vendor=%s model=%s firmware=%s",
            charge_point_vendor,
            charge_point_model,
            firmware_version,
        )
        self._services.events.publish(StateChangeEvent(self.id, None, None))
        return ocpp_call_result.BootNotification(
            current_time=_to_iso(boot_at),
            interval=self._services.heartbeat_interval_seconds,
            status=ocpp_enums.RegistrationStatus.accepted,
        )

    @on(ocpp_enums.Action.heartbeat)
    @_log_handler_errors
    async def on_heartbeat(self, **kwargs: object) -> ocpp_call_result.Heartbeat:
        """Handle Heartbeat.req: record it, reply with the current server time."""
        now = _utcnow()
        self._services.registry.mark_heartbeat(self.id, now)
        self._services.events.publish(StateChangeEvent(self.id, None, None))
        return ocpp_call_result.Heartbeat(current_time=_to_iso(now))

    @on(ocpp_enums.Action.status_notification)
    @_log_handler_errors
    async def on_status_notification(
        self,
        connector_id: int,
        error_code: str,
        status: str,
        **kwargs: object,
    ) -> ocpp_call_result.StatusNotification:
        """Handle StatusNotification.req: update connector state and publish it."""
        self._services.connectors.update(self.id, connector_id, status=status, error_code=error_code)
        self.cp_logger.info(
            "StatusNotification: connector=%s status=%s errorCode=%s",
            connector_id,
            status,
            error_code,
        )
        self._services.events.publish(StateChangeEvent(self.id, connector_id, None))
        return ocpp_call_result.StatusNotification()

    @on(ocpp_enums.Action.authorize)
    @_log_handler_errors
    async def on_authorize(self, id_tag: str, **kwargs: object) -> ocpp_call_result.Authorize:
        """Handle Authorize.req: return the idTag's authorization status."""
        decision = self._services.authorization.authorize(id_tag)
        self.cp_logger.info("Authorize idTag=%s -> %s", _mask_id_tag(id_tag), decision.status.value)
        return ocpp_call_result.Authorize(id_tag_info=_to_id_tag_info(decision))

    @on(ocpp_enums.Action.start_transaction)
    @_log_handler_errors
    async def on_start_transaction(
        self,
        connector_id: int,
        id_tag: str,
        meter_start: int,
        timestamp: str,
        **kwargs: object,
    ) -> ocpp_call_result.StartTransaction:
        """Handle StartTransaction.req: open a transaction and return its id."""
        meter_start = self._round_meter_value(meter_start, field_name="meterStart", action="StartTransaction")
        decision = self._services.authorization.authorize(id_tag)
        transaction = self._services.transactions.start_transaction(
            charge_point_id=self.id,
            connector_id=connector_id,
            id_tag=id_tag,
            meter_start_wh=meter_start,
            started_at=_parse_timestamp(timestamp),
        )
        self.cp_logger.info(
            "Transaktion %s gestartet: connector=%s idTag=%s meterStart=%s idTagStatus=%s",
            transaction.transaction_id,
            connector_id,
            _mask_id_tag(id_tag),
            meter_start,
            decision.status.value,
        )
        self._services.events.publish(StateChangeEvent(self.id, connector_id, transaction.transaction_id))
        return ocpp_call_result.StartTransaction(
            transaction_id=transaction.transaction_id,
            id_tag_info=_to_id_tag_info(decision),
        )

    @on(ocpp_enums.Action.stop_transaction)
    @_log_handler_errors
    async def on_stop_transaction(
        self,
        meter_stop: int,
        timestamp: str,
        transaction_id: int,
        reason: str | None = None,
        id_tag: str | None = None,
        transaction_data: list[dict] | None = None,
        **kwargs: object,
    ) -> ocpp_call_result.StopTransaction:
        """Handle StopTransaction.req: close the transaction and record its meter values."""
        meter_stop = self._round_meter_value(meter_stop, field_name="meterStop", action="StopTransaction")
        transaction = self._services.transactions.stop_transaction(
            transaction_id,
            meter_stop_wh=meter_stop,
            stopped_at=_parse_timestamp(timestamp),
            reason=reason,
        )
        if transaction is None:
            # REQ-0007 AC3: unbekannte transactionId -> trotzdem gültiges
            # CallResult, Abweichung nur protokollieren, Verbindung bleibt
            # bestehen.
            self.cp_logger.warning(
                "StopTransaction für unbekannte transactionId=%s empfangen",
                transaction_id,
            )
            connector_id = None
        else:
            connector_id = transaction.connector_id
            self.cp_logger.info(
                "Transaktion %s beendet: meterStop=%s reason=%s",
                transaction_id,
                meter_stop,
                reason,
            )
            self._services.events.publish(StateChangeEvent(self.id, connector_id, transaction_id))

        if transaction_data:
            samples = _extract_meter_samples(transaction_data)
            if connector_id is not None:
                self._services.meter_values.record(
                    charge_point_id=self.id,
                    connector_id=connector_id,
                    transaction_id=transaction_id,
                    samples=samples,
                )

        id_tag_info = None
        if id_tag is not None:
            decision = self._services.authorization.authorize(id_tag)
            id_tag_info = _to_id_tag_info(decision)
        return ocpp_call_result.StopTransaction(id_tag_info=id_tag_info)

    @on(ocpp_enums.Action.meter_values)
    @_log_handler_errors
    async def on_meter_values(
        self,
        connector_id: int,
        meter_value: list[dict],
        transaction_id: int | None = None,
        **kwargs: object,
    ) -> ocpp_call_result.MeterValues:
        """Handle MeterValues.req: record the reported samples."""
        samples = _extract_meter_samples(meter_value)
        self._services.meter_values.record(
            charge_point_id=self.id,
            connector_id=connector_id,
            transaction_id=transaction_id,
            samples=samples,
        )
        self.cp_logger.debug(
            "MeterValues: connector=%s transaction=%s samples=%d",
            connector_id,
            transaction_id,
            len(samples),
        )
        self._services.events.publish(StateChangeEvent(self.id, connector_id, transaction_id))
        return ocpp_call_result.MeterValues()

    # -- Central-System-initiierte Aufrufe (REQ-0009/0010/0012/0013/0014) ---

    async def remote_start_transaction(self, connector_id: int | None, id_tag: str) -> str:
        """Send RemoteStartTransaction.req and return its status."""
        response = _expect_response(
            await self.call(ocpp_call.RemoteStartTransaction(id_tag=id_tag, connector_id=connector_id))
        )
        return str(response.status)

    async def remote_stop_transaction(self, transaction_id: int) -> str:
        """Send RemoteStopTransaction.req and return its status."""
        response = _expect_response(await self.call(ocpp_call.RemoteStopTransaction(transaction_id=transaction_id)))
        return str(response.status)

    async def reset(self, reset_type: str) -> str:
        """Send Reset.req and return its status."""
        response = _expect_response(await self.call(ocpp_call.Reset(type=ocpp_enums.ResetType(reset_type))))
        return str(response.status)

    async def unlock_connector(self, connector_id: int) -> str:
        """Send UnlockConnector.req and return its status."""
        response = _expect_response(await self.call(ocpp_call.UnlockConnector(connector_id=connector_id)))
        return str(response.status)

    async def get_configuration(self, keys: Sequence[str] | None) -> tuple[list[dict], list[str]]:
        """Send GetConfiguration.req and return (known entries, unknown keys)."""
        response = _expect_response(await self.call(ocpp_call.GetConfiguration(key=list(keys) if keys else None)))
        return list(response.configuration_key or []), list(response.unknown_key or [])

    async def change_configuration(self, key: str, value: str) -> str:
        """Send ChangeConfiguration.req and return its status."""
        response = _expect_response(await self.call(ocpp_call.ChangeConfiguration(key=key, value=value)))
        return str(response.status)

    async def set_charging_profile(
        self,
        connector_id: int,
        charging_profile_id: int,
        limit_watts: float,
        number_phases: int | None = None,
    ) -> str:
        """Send SetChargingProfile.req with a TxDefaultProfile power limit."""
        # REQ-0023 v1: ausschließlich TxDefaultProfile, stackLevel 0, ein
        # sofort und dauerhaft wirksames chargingSchedulePeriod (kein
        # Zeitplan/Wiederholung, siehe ADR-0006). numberPhases (ADR-0006,
        # Ergänzung 2026-08-15b) wird nur bei explizitem Wert mitgeschickt --
        # CommandService hat den Wertebereich 1-3 bereits geprüft.
        period = (
            ocpp_datatypes.ChargingSchedulePeriod(start_period=0, limit=limit_watts, number_phases=number_phases)
            if number_phases is not None
            else ocpp_datatypes.ChargingSchedulePeriod(start_period=0, limit=limit_watts)
        )
        profile = ocpp_datatypes.ChargingProfile(
            charging_profile_id=charging_profile_id,
            stack_level=0,
            charging_profile_purpose=ocpp_enums.ChargingProfilePurposeType.tx_default_profile,
            charging_profile_kind=ocpp_enums.ChargingProfileKindType.absolute,
            charging_schedule=ocpp_datatypes.ChargingSchedule(
                charging_rate_unit=ocpp_enums.ChargingRateUnitType.watts,
                charging_schedule_period=[period],
            ),
        )
        response = _expect_response(
            await self.call(ocpp_call.SetChargingProfile(connector_id=connector_id, cs_charging_profiles=profile))
        )
        return str(response.status)

    async def clear_charging_profile(self, connector_id: int) -> str:
        """Send ClearChargingProfile.req for the connector's TxDefaultProfile."""
        # Kombinationsfilter statt id-Filter (ADR-0006): trifft fachlich
        # "das TxDefaultProfile an diesem Connector", unabhängig von der
        # chargingProfileId-Formel.
        response = _expect_response(
            await self.call(
                ocpp_call.ClearChargingProfile(
                    connector_id=connector_id,
                    charging_profile_purpose=ocpp_enums.ChargingProfilePurposeType.tx_default_profile,
                    stack_level=0,
                )
            )
        )
        return str(response.status)

    async def get_composite_schedule(self, connector_id: int, duration_seconds: int) -> CompositeScheduleResult:
        """Send GetCompositeSchedule.req and return the parsed schedule."""
        # REQ-0023 v1: chargingRateUnit fest 'W' angefragt (kein Ampere).
        response = _expect_response(
            await self.call(
                ocpp_call.GetCompositeSchedule(
                    connector_id=connector_id,
                    duration=duration_seconds,
                    charging_rate_unit=ocpp_enums.ChargingRateUnitType.watts,
                )
            )
        )
        status = str(response.status)
        schedule = response.charging_schedule
        if schedule is None:
            return CompositeScheduleResult(
                status=status,
                connector_id=response.connector_id,
                schedule_start=(_parse_timestamp(response.schedule_start) if response.schedule_start else None),
            )

        charging_rate_unit = schedule.get("charging_rate_unit")
        if charging_rate_unit is not None and charging_rate_unit != ocpp_enums.ChargingRateUnitType.watts.value:
            # Der Charge Point ist laut Spezifikation nicht zwingend an die
            # angefragte Einheit gebunden. Eine Ampere-Watt-Umrechnung
            # bräuchte Spannung/Phasenzahl, die hier nicht zuverlässig
            # vorliegen (REQ-0023 Non-Goal) -- statt die rohe Zahl fälschlich
            # als Watt auszugeben, liefert dieser Aufruf periods=[] zurück,
            # sodass der Aufrufer (ADR-0010, Fähigkeit 5) den Zustand als
            # unbekannt statt als falschen Wert behandelt (ADR-0006, analog
            # zum Rundungs-Log aus ADR-0005).
            self.cp_logger.warning(
                "GetCompositeSchedule: Charge Point meldet chargingRateUnit=%s "
                "statt der angefragten 'W', keine Umrechnung -- Periods verworfen (ADR-0006)",
                charging_rate_unit,
            )
            return CompositeScheduleResult(
                status=status,
                connector_id=response.connector_id,
                schedule_start=(_parse_timestamp(response.schedule_start) if response.schedule_start else None),
                duration_seconds=schedule.get("duration"),
                charging_rate_unit=charging_rate_unit,
            )

        periods = [
            ChargingSchedulePeriodInfo(
                start_offset_seconds=int(period["start_period"]),
                # python-ocpp parst GetCompositeSchedule-Antworten bewusst mit
                # decimal.Decimal statt float (Workaround gegen JSON-Schema-
                # Rundungsprobleme bei Fließkommazahlen, siehe ocpp.messages.
                # _validate_payload) -- an der ocpp16-Grenze auf den in
                # ADR-0006 dokumentierten float-Vertrag zurückführen.
                limit_watts=float(period["limit"]),
            )
            for period in schedule.get("charging_schedule_period", [])
        ]
        return CompositeScheduleResult(
            status=status,
            connector_id=response.connector_id,
            schedule_start=(_parse_timestamp(response.schedule_start) if response.schedule_start else None),
            duration_seconds=schedule.get("duration"),
            charging_rate_unit=charging_rate_unit,
            periods=periods,
        )

    async def change_availability(self, connector_id: int, availability_type: str) -> str:
        """Send ChangeAvailability.req and return its status."""
        response = _expect_response(
            await self.call(
                ocpp_call.ChangeAvailability(
                    connector_id=connector_id, type=ocpp_enums.AvailabilityType(availability_type)
                )
            )
        )
        return str(response.status)

    async def trigger_message(self, requested_message: str, connector_id: int | None) -> str:
        """Send TriggerMessage.req and return its status."""
        response = _expect_response(
            await self.call(
                ocpp_call.TriggerMessage(
                    requested_message=ocpp_enums.MessageTrigger(requested_message), connector_id=connector_id
                )
            )
        )
        return str(response.status)

    async def get_diagnostics(
        self,
        location: str,
        *,
        retries: int | None,
        retry_interval: int | None,
        start_time: str | None,
        stop_time: str | None,
    ) -> str | None:
        """Send GetDiagnostics.req and return the reported file name, if any."""
        response = _expect_response(
            await self.call(
                ocpp_call.GetDiagnostics(
                    location=location,
                    retries=retries,
                    retry_interval=retry_interval,
                    start_time=start_time,
                    stop_time=stop_time,
                )
            )
        )
        return response.file_name
