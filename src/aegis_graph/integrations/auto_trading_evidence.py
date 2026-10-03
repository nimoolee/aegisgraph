"""Read-only evidence adapter for the 99safe automatic trading reference system.

This module does not decide whether the target is correct. It only translates
observed target state/ledger facts into AegisGraph fact values with provenance.
The semantic graph + invariants remain the authority for PASS/FAIL/UNKNOWN.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
import hashlib
import json
from pathlib import Path
import subprocess
from typing import Any


@dataclass(frozen=True, slots=True)
class EvidenceSnapshot:
    target_root: str
    snapshot_id: str
    commit_sha: str | None
    dirty_worktree: bool | None
    fact_values: dict[str, Any]
    sources: dict[str, tuple[str, ...]]
    warnings: tuple[str, ...] = ()


def _decimal(value: Any) -> Decimal | None:
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None
    return parsed if parsed.is_finite() else None


def _git_identity(root: Path) -> tuple[str | None, bool | None]:
    try:
        head = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout.strip()
        dirty = bool(
            subprocess.run(
                ["git", "-C", str(root), "status", "--porcelain"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            ).stdout.strip()
        )
        return head or None, dirty
    except (OSError, subprocess.SubprocessError):
        return None, None


def _load_json(path: Path) -> dict[str, Any]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"expected object in {path}")
    return raw


def _ledger_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _latest_mixed_token(state: dict[str, Any]) -> str | None:
    fills = state.get("bot_buy_fills")
    funding = state.get("manual_funding")
    if not isinstance(fills, dict) or not isinstance(funding, dict):
        return None
    candidates: list[tuple[int, str]] = []
    for token, fill in fills.items():
        if not isinstance(fill, dict) or token not in funding:
            continue
        shares = _decimal(fill.get("sell_receipt_shares"))
        if shares is None:
            shares = _decimal(fill.get("mixed_sell_receipt_shares"))
        if shares is None or shares <= 0:
            continue
        candidates.append((int(fill.get("response_ms") or 0), str(token)))
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
    signal = row.get("signal") if isinstance(row.get("signal"), dict) else {}
    round_id = str(row.get("round_id") or signal.get("round_id") or "")
    if not round_id:
        return None
    if row.get("kind") == "ORDER_SUBMIT":
        decision = "BUY"
    else:
        action = str(row.get("decision") or "BLOCKED").upper()
        reason = str(row.get("reason") or "")
        decision = f"BLOCKED:{reason}" if action == "BLOCKED" and reason else action
    bot_positions = state.get("bot_positions") if isinstance(state.get("bot_positions"), dict) else {}
    bot_same_round = any(
        isinstance(pos, dict) and str(pos.get("round_id") or "") == round_id
        for pos in bot_positions.values()
    ) or any(
        isinstance(pos, dict) and str(pos.get("round_id") or "") == round_id
        for pos in (state.get("pending_settlements") or [])
    )
    already_submitted = round_id in (state.get("fired_rounds") or [])
    return round_id, bot_same_round, already_submitted, decision


def collect_evidence(target_root: str | Path) -> EvidenceSnapshot:
    """Collect target evidence without mutating the target project."""

    root = Path(target_root).expanduser().resolve()
    state_path = root / "runtime" / "live_test_state.json"
    ledger_path = root / "runtime" / "live_test_orders.jsonl"
    if not state_path.is_file() or not ledger_path.is_file():
        raise FileNotFoundError("auto-trading runtime state/ledger not found")

    state = _load_json(state_path)
    rows = _ledger_rows(ledger_path)
    commit_sha, dirty = _git_identity(root)
    facts: dict[str, Any] = {}
    sources: dict[str, tuple[str, ...]] = {}
    warnings: list[str] = []

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
    put("auto.order.minimum", 5, "99safe SAFE_TRADE minimum executable order")
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

    token = _latest_mixed_token(state)
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

        pending = state.get("settlement_cash_sync_pending")
        same_pending = isinstance(pending, dict) and (
            str(pending.get("round_id") or "") == str(funding.get("round_id") or "")
            or str(pending.get("condition_id") or "") == str(funding.get("condition_id") or "")
        )
        put("auto.settlement.pending", bool(same_pending), "runtime/live_test_state.json:settlement_cash_sync_pending")
        if same_pending:
            put("auto.settlement.expected_redeem_shares", pending.get("expected_payout"), "runtime/live_test_state.json:settlement_cash_sync_pending.expected_payout")
        else:
            put("auto.settlement.expected_redeem_shares", 0, "no matching settlement_cash_sync_pending remains")

    fingerprint = hashlib.sha256()
    fingerprint.update(state_path.read_bytes())
    fingerprint.update(str(ledger_path.stat().st_size).encode())
    fingerprint.update(str(ledger_path.stat().st_mtime_ns).encode())
    snapshot_id = fingerprint.hexdigest()[:16]
    return EvidenceSnapshot(
        target_root=str(root),
        snapshot_id=snapshot_id,
        commit_sha=commit_sha,
        dirty_worktree=dirty,
        fact_values=facts,
        sources=sources,
        warnings=tuple(warnings),
    )
