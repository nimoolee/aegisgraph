"""Append-only local audit trail for real AegisGraph executions.

The audit trail records Aegis executions, not ChatGPT/plugin UI mentions. It lives in
AegisGraph's ignored runtime directory so target repositories remain untouched.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Iterable

DEFAULT_AUDIT_PATH = Path("runtime/aegis-invocations.jsonl")


@dataclass(frozen=True, slots=True)
class InvocationRecord:
    timestamp: str
    mode: str
    target: str
    source: str = "aegis"
    status: str = "completed"
    verdict: str | None = None
    evidence_snapshot_id: str | None = None
    target_commit: str | None = None
    duration_ms: int | None = None
    note: str | None = None


def new_record(*, mode: str, target: str, source: str = "aegis", status: str = "completed", verdict: str | None = None, evidence_snapshot_id: str | None = None, target_commit: str | None = None, duration_ms: int | None = None, note: str | None = None) -> InvocationRecord:
    return InvocationRecord(
        timestamp=datetime.now(timezone.utc).isoformat(),
        mode=mode,
        target=str(Path(target).expanduser()),
        source=source,
        status=status,
        verdict=verdict.lower() if verdict else None,
        evidence_snapshot_id=evidence_snapshot_id,
        target_commit=target_commit,
        duration_ms=duration_ms,
        note=note,
    )


def append_invocation(record: InvocationRecord, path: str | Path = DEFAULT_AUDIT_PATH) -> Path:
    output = Path(path).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n")
    return output


def load_invocations(path: str | Path = DEFAULT_AUDIT_PATH, *, limit: int | None = None) -> tuple[InvocationRecord, ...]:
    source = Path(path).expanduser().resolve()
    if not source.exists():
        return ()
    records: list[InvocationRecord] = []
    for raw in source.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        try:
            records.append(InvocationRecord(**json.loads(raw)))
        except (json.JSONDecodeError, TypeError):
            continue
    if limit is not None:
        records = records[-max(0, limit):]
    return tuple(records)


def summarize_invocations(records: Iterable[InvocationRecord]) -> dict[str, object]:
    rows = tuple(records)
    verdict_counts = {"pass": 0, "fail": 0, "unknown": 0}
    mode_counts: dict[str, int] = {}
    for row in rows:
        mode_counts[row.mode] = mode_counts.get(row.mode, 0) + 1
        if row.verdict in verdict_counts:
            verdict_counts[row.verdict] += 1
    return {
        "total": len(rows),
        "pass": verdict_counts["pass"],
        "fail": verdict_counts["fail"],
        "unknown": verdict_counts["unknown"],
        "modes": dict(sorted(mode_counts.items())),
        "last_run": asdict(rows[-1]) if rows else None,
    }
