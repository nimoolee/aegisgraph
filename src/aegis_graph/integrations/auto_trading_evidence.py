"""Read-only evidence adapter for the sanitized Auto Trading reference system.

This module does not decide whether the target is correct. It only translates
observed target state/ledger facts into AegisGraph fact values with provenance.
The semantic graph + invariants remain the authority for PASS/FAIL/UNKNOWN.
"""

from __future__ import annotations

import hashlib
import json
import shutil

# Subprocess is restricted to an absolute Git executable with literal argv and no shell.
import subprocess  # nosec B404
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, cast

from aegis_graph.immutability import freeze_mapping

MAX_STATE_BYTES = 16 * 1024 * 1024
MAX_LEDGER_LINE_BYTES = 4 * 1024 * 1024


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    target_root: str
    snapshot_id: str
    commit_sha: str | None
    dirty_worktree: bool | None
    fact_values: Mapping[str, Any]
    sources: Mapping[str, tuple[str, ...]]
    complete: bool = True
    warnings: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "fact_values", freeze_mapping(self.fact_values))
        object.__setattr__(
            self,
            "sources",
            cast(Mapping[str, tuple[str, ...]], freeze_mapping(self.sources)),
        )


def _decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _git_identity(root: Path) -> tuple[str | None, bool | None]:
    git = shutil.which("git")
    if git is None:
        return None, None
    try:
        # Absolute Git executable + literal argv; shell execution is never enabled.
        head = subprocess.run(  # nosec B603
            [git, "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(  # nosec B603
                [git, "-C", str(root), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
        return head or None, dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def _file_signature(path: Path) -> tuple[int, int, int, int] | None:
    """Return a cheap identity/change signature for one evidence file."""

    try:
        stat = path.stat()
    except OSError:
        return None
    return (stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns)


def _load_json(path: Path) -> tuple[dict[str, Any], bytes]:
    raw_bytes = path.read_bytes()
    size = len(raw_bytes)
    if size > MAX_STATE_BYTES:
        raise ValueError(
            f"state file exceeds {MAX_STATE_BYTES} byte safety limit: {size}"
        )
    raw = json.loads(raw_bytes.decode("utf-8"))
    if not isinstance(raw, dict):
        raise TypeError(f"expected object in {path}")
    return raw, hashlib.sha256(raw_bytes).digest()


def _ledger_rows(path: Path) -> tuple[list[dict[str, Any]], list[str], bytes | None]:
    rows: list[dict[str, Any]] = []
    integrity_warnings: list[str] = []
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                digest.update(raw_line)
                if len(raw_line) > MAX_LEDGER_LINE_BYTES:
                    integrity_warnings.append(
                        f"ledger line {line_number} exceeds {MAX_LEDGER_LINE_BYTES} byte safety limit"
                    )
                    continue
                try:
                    line = raw_line.decode("utf-8")
                except UnicodeDecodeError as exc:
                    integrity_warnings.append(
                        f"ledger line {line_number} invalid UTF-8: {exc}"
                    )
                    continue
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    integrity_warnings.append(
                        f"ledger line {line_number} malformed JSON: {exc.msg}"
                    )
                    continue
                if not isinstance(row, dict):
                    integrity_warnings.append(
                        f"ledger line {line_number} is not a JSON object"
                    )
                    continue
                rows.append(row)
    except OSError as exc:
        return rows, [f"ledger unreadable: {type(exc).__name__}: {exc}"], None
    return rows, integrity_warnings, digest.digest()


def _latest_mixed_token(
    state: dict[str, Any], integrity_warnings: list[str]
) -> str | None:
    fills = state.get("bot_buy_fills")
    funding = state.get("manual_funding")
    if not isinstance(fills, dict) or not isinstance(funding, dict):
        return None
    candidates: list[tuple[Decimal, str]] = []
    for token, fill in fills.items():
        if not isinstance(fill, dict) or token not in funding:
            continue
        shares = _decimal(fill.get("sell_receipt_shares"))
        if shares is None:
            shares = _decimal(fill.get("mixed_sell_receipt_shares"))
        if shares is None or shares <= 0:
            continue
        response_raw = fill.get("response_ms")
        response_ms = _decimal(response_raw)
        if response_raw not in (None, "", 0) and response_ms is None:
            integrity_warnings.append(
                f"bot_buy_fills[{token}].response_ms is not a finite number"
            )
            continue
        candidates.append((response_ms or Decimal("0"), str(token)))
    return max(candidates)[1] if candidates else None


def _physical_sell_proceeds(rows: list[dict[str, Any]], token: str) -> Decimal | None:
    # MANUAL_CASH_RETURN.activity_key preserves the raw TRADE usdcSize as its final
    # component. It is therefore observed physical receipt evidence, not a value
    # reconstructed from manual+bot logical attribution.
    candidates = [
        row for row in rows
        if row.get("kind") == "MANUAL_CASH_RETURN"
        and str(row.get("token_id") or "") == token
        and str(row.get("return_type") or "") == "TRADE"
    ]
    for row in reversed(candidates):
        key = str(row.get("activity_key") or "")
        if key:
            value = _decimal(key.rsplit("|", 1)[-1])
            if value is not None:
                return value
    return None


def _latest_execution_evidence(
    state: dict[str, Any], rows: list[dict[str, Any]]
) -> tuple[str, bool, bool, str] | None:
    """Return the latest persisted execution decision and its current coverage facts."""
    candidates = [row for row in rows if row.get("kind") in {"ORDER_SUBMIT", "ORDER_BLOCKED"}]
    if not candidates:
        return None
    row = candidates[-1]
    signal_raw = row.get("signal")
    signal: dict[str, Any] = signal_raw if isinstance(signal_raw, dict) else {}
    round_id = str(row.get("round_id") or signal.get("round_id") or "")
    if not round_id:
        return None
    if row.get("kind") == "ORDER_SUBMIT":
        decision = "BUY"
    else:
        action = str(row.get("decision") or "BLOCKED").upper()
        reason = str(row.get("reason") or "")
        decision = f"BLOCKED:{reason}" if action == "BLOCKED" and reason else action
    bot_positions_raw = state.get("bot_positions")
    bot_positions: dict[str, Any] = (
        bot_positions_raw if isinstance(bot_positions_raw, dict) else {}
    )
    pending_raw = state.get("pending_settlements")
    pending_settlements: list[Any] = pending_raw if isinstance(pending_raw, list) else []
    bot_same_round = any(
        isinstance(pos, dict) and str(pos.get("round_id") or "") == round_id
        for pos in bot_positions.values()
    ) or any(
        isinstance(pos, dict) and str(pos.get("round_id") or "") == round_id
        for pos in pending_settlements
    )
    already_submitted = round_id in (state.get("fired_rounds") or [])
    return round_id, bot_same_round, already_submitted, decision


def collect_evidence(target_root: str | Path) -> EvidenceSnapshot:
    """Collect target evidence without mutating the target project."""

    root = Path(target_root).expanduser().resolve()
    state_path = root / "runtime" / "live_test_state.json"
    ledger_path = root / "runtime" / "live_test_orders.jsonl"
    integrity_warnings: list[str] = []

    state: dict[str, Any] = {}
    state_signature_before = _file_signature(state_path)
    ledger_signature_before = _file_signature(ledger_path)

    state_digest: bytes | None = None
    if state_path.is_file():
        try:
            state, state_digest = _load_json(state_path)
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            integrity_warnings.append(
                f"state unreadable: {type(exc).__name__}: {exc}"
            )
    else:
        integrity_warnings.append("runtime/live_test_state.json is missing")

    ledger_digest: bytes | None = None
    if ledger_path.is_file():
        rows, ledger_warnings, ledger_digest = _ledger_rows(ledger_path)
        integrity_warnings.extend(ledger_warnings)
    else:
        rows = []
        integrity_warnings.append("runtime/live_test_orders.jsonl is missing")

    state_signature_after = _file_signature(state_path)
    ledger_signature_after = _file_signature(ledger_path)
    if state_signature_before != state_signature_after:
        integrity_warnings.append("state changed during evidence collection")
    if ledger_signature_before != ledger_signature_after:
        integrity_warnings.append("ledger changed during evidence collection")

    expected_state_types: dict[str, type | tuple[type, ...]] = {
        "bot_positions": dict,
        "pending_settlements": list,
        "position": (dict, type(None)),
        "external_positions": dict,
        "manual_funding": dict,
        "bot_buy_fills": dict,
        "fired_rounds": list,
        "settlement_cash_sync_pending": (dict, type(None)),
        "manual_funding_detection_pending": bool,
        "unattributed_cash_outflow_guard": bool,
    }
    for field_name, expected_type in expected_state_types.items():
        if field_name in state and not isinstance(state[field_name], expected_type):
            integrity_warnings.append(
                f"state field {field_name} has invalid type {type(state[field_name]).__name__}"
            )

    for field_name in (
        "account_balance",
        "trade_account_balance",
        "safe_account_balance",
        "orderable_balance",
        "cash_inflow_unattributed",
        "manual_cash_pending",
    ):
        if field_name in state and _decimal(state[field_name]) is None:
            integrity_warnings.append(
                f"state field {field_name} is not a finite numeric value"
            )

    for container_name in ("manual_funding", "bot_buy_fills"):
        container = state.get(container_name)
        if not isinstance(container, dict):
            continue
        for record_key, record_value in container.items():
            if not isinstance(record_value, dict):
                integrity_warnings.append(
                    f"state field {container_name}[{record_key}] is not an object"
                )

    commit_sha, dirty = _git_identity(root)
    facts: dict[str, Any] = {}
    sources: dict[str, tuple[str, ...]] = {}
    warnings: list[str] = list(integrity_warnings)

    def put(fact_id: str, value: Any, *origin: str) -> None:
        if value is not None:
            facts[fact_id] = value
            sources[fact_id] = tuple(origin)

    put("auto.cash.trading", state.get("trade_account_balance"), "runtime/live_test_state.json:trade_account_balance")
    put("auto.cash.clob_free", state.get("account_balance"), "runtime/live_test_state.json:account_balance")
    put("auto.cash.safety", state.get("safe_account_balance"), "runtime/live_test_state.json:safe_account_balance")
    bot_positions = state.get("bot_positions") if isinstance(state.get("bot_positions"), dict) else {}
    pending_settlements = state.get("pending_settlements") if isinstance(state.get("pending_settlements"), list) else []
    legacy_position = state.get("position") if isinstance(state.get("position"), dict) else None
    positive_unattributed = _decimal(state.get("cash_inflow_unattributed")) or Decimal("0")
    manual_cash_pending = _decimal(state.get("manual_cash_pending")) or Decimal("0")
    attribution_in_flight = bool(
        positive_unattributed > Decimal("0.00001")
        or manual_cash_pending > Decimal("0.00001")
        or state.get("manual_funding_detection_pending")
        or state.get("unattributed_cash_outflow_guard")
    )
    capital_flat = not bool(
        bot_positions or pending_settlements or legacy_position
        or state.get("settlement_cash_sync_pending")
        or (state.get("external_positions") if isinstance(state.get("external_positions"), dict) else {})
        or attribution_in_flight
    )
    put("auto.capital.flat", capital_flat, "runtime/live_test_state.json:live ownership/settlement state")
    put("auto.cash.orderable", state.get("orderable_balance"), "runtime/live_test_state.json:orderable_balance")
    put("auto.order.minimum", 5, "sanitized Auto Trading reference minimum executable order")
    external = state.get("external_positions")
    put("auto.position.manual_exists", bool(external) if isinstance(external, dict) else False, "runtime/live_test_state.json:external_positions")

    execution = _latest_execution_evidence(state, rows)
    if execution is None:
        warnings.append("no persisted ORDER_SUBMIT/ORDER_BLOCKED execution evidence found")
    else:
        execution_round, bot_same_round, already_submitted, decision = execution
        put("auto.position.bot_same_round", bot_same_round, f"runtime/live_test_state.json:bot_positions/pending_settlements for {execution_round}")
        put("auto.order.already_submitted", already_submitted, f"runtime/live_test_state.json:fired_rounds for {execution_round}")
        put("auto.signal.execution_decision", decision, f"runtime/live_test_orders.jsonl:latest execution event for {execution_round}")

    token = _latest_mixed_token(state, integrity_warnings)
    if token is None:
        warnings.append("no mixed manual+bot SELL evidence found in current persisted state")
    else:
        funding = (state.get("manual_funding") or {}).get(token) or {}
        fill = (state.get("bot_buy_fills") or {}).get(token) or {}
        physical_proceeds = _physical_sell_proceeds(rows, token)
        physical_shares = _decimal(funding.get("physical_sold_shares_observed"))
        physical_source = f"runtime/live_test_state.json:manual_funding[{token}].physical_sold_shares_observed"
        if physical_shares is None:
            physical_shares = _decimal(funding.get("activity_sold_shares"))
            physical_source = f"runtime/live_test_state.json:manual_funding[{token}].activity_sold_shares (legacy raw SELL-derived)"
        manual_total = _decimal(funding.get("activity_buy_shares"))
        manual_sold = _decimal(funding.get("activity_sold_shares"))
        bot_total = _decimal(fill.get("filled_shares"))
        bot_sold = _decimal(fill.get("sell_receipt_shares"))
        bot_sold_source = f"runtime/live_test_state.json:bot_buy_fills[{token}].sell_receipt_shares"
        if bot_sold is None:
            bot_sold = _decimal(fill.get("mixed_sell_receipt_shares"))
            bot_sold_source = f"runtime/live_test_state.json:bot_buy_fills[{token}].mixed_sell_receipt_shares (legacy)"
        manual_proceeds = _decimal(funding.get("cash_returned"))
        bot_proceeds = _decimal(fill.get("sell_receipt_proceeds"))
        bot_proceeds_source = f"runtime/live_test_state.json:bot_buy_fills[{token}].sell_receipt_proceeds"
        if bot_proceeds is None:
            bot_proceeds = _decimal(fill.get("mixed_sell_receipt_proceeds"))
            bot_proceeds_source = f"runtime/live_test_state.json:bot_buy_fills[{token}].mixed_sell_receipt_proceeds (legacy)"

        put("auto.position.physical_sell_shares", physical_shares, physical_source)
        put("auto.position.manual_total_shares", manual_total, f"runtime/live_test_state.json:manual_funding[{token}].activity_buy_shares")
        put("auto.position.manual_sell_shares", manual_sold, f"runtime/live_test_state.json:manual_funding[{token}].activity_sold_shares (current manual attribution record)")
        put("auto.position.bot_total_shares", bot_total, f"runtime/live_test_state.json:bot_buy_fills[{token}].filled_shares")
        put("auto.position.bot_sold_shares", bot_sold, bot_sold_source)
        put("auto.position.unknown_sell_shares", 0, "no persisted UNKNOWN ownership bucket for this mixed SELL")
        put("auto.cash.physical_sell_proceeds", physical_proceeds, "runtime/live_test_orders.jsonl:MANUAL_CASH_RETURN.activity_key raw TRADE usdcSize")
        put("auto.cash.manual_sell_proceeds", manual_proceeds, f"runtime/live_test_state.json:manual_funding[{token}].cash_returned")
        put("auto.cash.bot_sell_proceeds", bot_proceeds, bot_proceeds_source)
        put("auto.cash.unknown_sell_proceeds", 0, "no persisted UNKNOWN cash attribution for this mixed SELL")
        put("auto.settlement.mixed_sell_verified", bool(bot_sold is not None and bot_sold > 0), bot_sold_source)

        pending_raw = state.get("settlement_cash_sync_pending")
        pending: dict[str, Any] | None = (
            pending_raw if isinstance(pending_raw, dict) else None
        )
        same_pending = pending is not None and (
            str(pending.get("round_id") or "") == str(funding.get("round_id") or "")
            or str(pending.get("condition_id") or "")
            == str(funding.get("condition_id") or "")
        )
        put("auto.settlement.pending", bool(same_pending), "runtime/live_test_state.json:settlement_cash_sync_pending")
        if same_pending and pending is not None:
            put("auto.settlement.expected_redeem_shares", pending.get("expected_payout"), "runtime/live_test_state.json:settlement_cash_sync_pending.expected_payout")
        else:
            put("auto.settlement.expected_redeem_shares", 0, "no matching settlement_cash_sync_pending remains")

    fingerprint = hashlib.sha256()
    if state_digest is not None:
        fingerprint.update(state_digest)
    elif state_path.is_file():
        fingerprint.update(b"unreadable-state")
    else:
        fingerprint.update(b"missing-state")
    if ledger_digest is not None:
        fingerprint.update(ledger_digest)
    elif ledger_path.is_file():
        fingerprint.update(b"unreadable-ledger")
    else:
        fingerprint.update(b"missing-ledger")
    snapshot_id = fingerprint.hexdigest()[:16]
    return EvidenceSnapshot(
        target_root=str(root),
        snapshot_id=snapshot_id,
        commit_sha=commit_sha,
        dirty_worktree=dirty,
        fact_values=facts,
        sources=sources,
        complete=not integrity_warnings,
        warnings=tuple(dict.fromkeys((*integrity_warnings, *warnings))),
    )
