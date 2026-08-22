"""Interaktive Konsole (REQ-0032 Statusausgabe, REQ-0033 Steuerung).

ADR-0002: ``prompt_toolkit`` (``PromptSession.prompt_async()`` +
``patch_stdout()``), als eigener ``asyncio.Task`` im selben Event Loop, nur
gestartet, wenn ``sys.stdin.isatty()`` (siehe ``core.app.CentralSystemApp.run``).

Kommandoumfang v1 (Entscheidung REQ-0033): ausschließlich die bereits
spezifizierten Remote-Aktionen (REQ-0009/0010/0012/0013/0014) plus die
Statusübersicht (REQ-0032) — kein Bestätigungsschritt vor steuernden
Aktionen, kein für Skripte wiederverwendbares Format.
"""

from collections.abc import Awaitable, Callable, Sequence
import logging
import shlex
from typing import TYPE_CHECKING

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.patch_stdout import patch_stdout

from custom_components.ocpp16.core.domain.commands import CommandError
from custom_components.ocpp16.core.domain.models import ChargePointSnapshot, ConnectorSnapshot, TransactionSnapshot

if TYPE_CHECKING:
    from custom_components.ocpp16.core.app import CentralSystemApp

logger = logging.getLogger(__name__)


class ConsoleUsageError(Exception):
    """Syntaktisch ungültiges Kommando (REQ-0033 AC2/AC5)."""


async def _cmd_status(app: CentralSystemApp, args: list[str]) -> str:
    charge_points: Sequence[ChargePointSnapshot] = app.query_service.get_charge_points()
    if not charge_points:
        return "Keine Charge Points verbunden."

    lines: list[str] = []
    for cp in charge_points:
        lines.append(
            f"{cp.charge_point_id}  [{cp.connection_status.value}]  "
            f"vendor={cp.vendor or '-'} model={cp.model or '-'} "
            f"last_boot={cp.last_boot_at.isoformat() if cp.last_boot_at else '-'}"
        )
        connectors: Sequence[ConnectorSnapshot] = app.query_service.get_connectors(cp.charge_point_id)
        lines.extend(
            f"    connector {connector.connector_id}: {connector.status}"
            + (f" (errorCode={connector.error_code})" if connector.error_code else "")
            for connector in sorted(connectors, key=lambda c: c.connector_id)
        )
        transactions: Sequence[TransactionSnapshot] = app.query_service.get_active_transactions(cp.charge_point_id)
        lines.extend(
            f"    transaction {tx.transaction_id}: connector={tx.connector_id} "
            f"idTag={tx.id_tag} started={tx.started_at.isoformat()}"
            for tx in transactions
        )
    return "\n".join(lines)


def _require_args(args: list[str], count: int, usage: str) -> None:
    if len(args) != count:
        raise ConsoleUsageError(f"Usage: {usage}")


async def _cmd_start(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 3, "start <chargePointId> <connectorId|-> <idTag>")
    charge_point_id, connector_arg, id_tag = args
    connector_id = None if connector_arg == "-" else int(connector_arg)
    result = await app.command_service.remote_start_transaction(charge_point_id, connector_id, id_tag)
    return "Ladevorgang gestartet." if result.accepted else "Charge Point hat abgelehnt (Rejected)."


async def _cmd_stop(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 1, "stop <transactionId>")
    transaction_id = int(args[0])
    result = await app.command_service.remote_stop_transaction(transaction_id)
    return "Ladevorgang gestoppt." if result.accepted else "Charge Point hat abgelehnt (Rejected)."


async def _cmd_reset(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 2, "reset <chargePointId> <Soft|Hard>")
    charge_point_id, reset_type = args
    if reset_type not in ("Soft", "Hard"):
        raise ConsoleUsageError("reset_type muss 'Soft' oder 'Hard' sein.")
    result = await app.command_service.reset(charge_point_id, reset_type)
    return "Reset akzeptiert." if result.accepted else "Charge Point hat abgelehnt (Rejected)."


async def _cmd_unlock(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 2, "unlock <chargePointId> <connectorId>")
    charge_point_id, connector_arg = args
    result = await app.command_service.unlock_connector(charge_point_id, int(connector_arg))
    return f"Ergebnis: {result.status}"


async def _cmd_getconfig(app: CentralSystemApp, args: list[str]) -> str:
    if len(args) < 1:
        raise ConsoleUsageError("Usage: getconfig <chargePointId> [key ...]")
    charge_point_id, *keys = args
    result = await app.command_service.get_configuration(charge_point_id, keys or None)
    lines = [f"{entry.key} = {entry.value} (readonly={entry.readonly})" for entry in result.entries]
    if result.unknown_keys:
        lines.append(f"unbekannte Schlüssel: {', '.join(result.unknown_keys)}")
    return "\n".join(lines) if lines else "Keine Konfigurationswerte gemeldet."


async def _cmd_setconfig(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 3, "setconfig <chargePointId> <key> <value>")
    charge_point_id, key, value = args
    result = await app.command_service.change_configuration(charge_point_id, key, value)
    if result.status == "RebootRequired":
        return "Angenommen — wird erst nach einem Neustart der Ladestation wirksam."
    return f"Ergebnis: {result.status}"


async def _cmd_setlimit(app: CentralSystemApp, args: list[str]) -> str:
    if not 3 <= len(args) <= 4:
        raise ConsoleUsageError("Usage: setlimit <chargePointId> <connectorId> <watt> [numberPhases]")
    charge_point_id, connector_arg, watt_arg, *number_phases_arg = args
    number_phases = int(number_phases_arg[0]) if number_phases_arg else None
    result = await app.command_service.set_charging_profile(
        charge_point_id, int(connector_arg), float(watt_arg), number_phases
    )
    return f"Ergebnis: {result.status} (chargingProfileId={result.charging_profile_id})"


async def _cmd_clearlimit(app: CentralSystemApp, args: list[str]) -> str:
    _require_args(args, 2, "clearlimit <chargePointId> <connectorId>")
    charge_point_id, connector_arg = args
    result = await app.command_service.clear_charging_profile(charge_point_id, int(connector_arg))
    return f"Ergebnis: {result.status}"


async def _cmd_getlimit(app: CentralSystemApp, args: list[str]) -> str:
    if not 2 <= len(args) <= 3:
        raise ConsoleUsageError("Usage: getlimit <chargePointId> <connectorId> [durationSeconds]")
    charge_point_id, connector_arg, *duration_arg = args
    kwargs = {"duration_seconds": int(duration_arg[0])} if duration_arg else {}
    result = await app.command_service.get_composite_schedule(charge_point_id, int(connector_arg), **kwargs)
    if result.status != "Accepted":
        return f"Ergebnis: {result.status}"
    if not result.periods:
        return "Ergebnis: Accepted (keine Zeitplan-Info gemeldet)"

    unit = result.charging_rate_unit or "W"
    start = result.schedule_start.isoformat() if result.schedule_start else "-"
    duration = result.duration_seconds if result.duration_seconds is not None else "-"
    lines = [f"Ergebnis: Accepted (Einheit={unit}, ab {start}, {duration}s)"]
    lines.extend(f"    ab +{period.start_offset_seconds}s: {period.limit_watts} {unit}" for period in result.periods)
    return "\n".join(lines)


async def _cmd_help(app: CentralSystemApp, args: list[str]) -> str:
    return _help_text()


_CommandHandler = Callable[["CentralSystemApp", list[str]], Awaitable[str]]

_COMMANDS: dict[str, _CommandHandler] = {
    "status": _cmd_status,
    "start": _cmd_start,
    "stop": _cmd_stop,
    "reset": _cmd_reset,
    "unlock": _cmd_unlock,
    "getconfig": _cmd_getconfig,
    "setconfig": _cmd_setconfig,
    "setlimit": _cmd_setlimit,
    "clearlimit": _cmd_clearlimit,
    "getlimit": _cmd_getlimit,
    "help": _cmd_help,
}


def _help_text() -> str:
    return (
        "Verfügbare Kommandos:\n"
        "  status                                       Statusübersicht\n"
        "  start <cpId> <connectorId|-> <idTag>          RemoteStartTransaction\n"
        "  stop <transactionId>                          RemoteStopTransaction\n"
        "  reset <cpId> <Soft|Hard>                       Reset\n"
        "  unlock <cpId> <connectorId>                    UnlockConnector\n"
        "  getconfig <cpId> [key ...]                     GetConfiguration\n"
        "  setconfig <cpId> <key> <value>                 ChangeConfiguration\n"
        "  setlimit <cpId> <connectorId> <watt> [numberPhases] SetChargingProfile (TxDefaultProfile)\n"
        "  clearlimit <cpId> <connectorId>                ClearChargingProfile\n"
        "  getlimit <cpId> <connectorId> [durationSeconds] GetCompositeSchedule\n"
        "  help                                            diese Übersicht"
    )


async def _dispatch(app: CentralSystemApp, line: str) -> str:
    try:
        tokens = shlex.split(line)
    except ValueError as exc:
        return f"Ungültige Eingabe: {exc}"
    if not tokens:
        return ""

    name, *args = tokens
    handler = _COMMANDS.get(name.lower())
    if handler is None:
        return f"Unbekanntes Kommando '{name}'.\n{_help_text()}"

    try:
        return await handler(app, args)
    except ConsoleUsageError as exc:
        return str(exc)
    except CommandError as exc:
        # REQ-0033 AC2: verständliche Fehlermeldung statt Absturz.
        return f"Fehler: {exc}"
    except ValueError as exc:
        return f"Ungültiges Argument: {exc}"
    except Exception:
        logger.exception("Unbehandelter Fehler bei Konsolenkommando: %s", line)
        return "Unerwarteter Fehler — siehe Log für Details."


async def run_console(app: CentralSystemApp) -> None:
    """Run the interactive console loop until EOF or Ctrl-C."""
    completer = WordCompleter(list(_COMMANDS.keys()), ignore_case=True)
    session: PromptSession[str] = PromptSession("ocpp> ", completer=completer)

    print("OCPP Standalone-Kern — interaktive Konsole. 'help' für Kommandos.")
    with patch_stdout():
        while True:
            try:
                line = await session.prompt_async()
            except EOFError, KeyboardInterrupt:
                print("Konsole beendet.")
                return

            line = line.strip()
            if not line:
                continue

            output = await _dispatch(app, line)
            if output:
                print(output)
