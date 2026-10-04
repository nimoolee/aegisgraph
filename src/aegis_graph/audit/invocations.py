"""Append-only local audit trail for real AegisGraph executions.

The audit trail records Aegis executions, not ChatGPT/plugin UI mentions. It lives in
AegisGraph's ignored runtime directory so target repositories remain untouched.
"""

from __future__ import annotations

import json
import os
import sys
import warnings
from collections import deque
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

MAX_AUDIT_LINE_BYTES = 1024 * 1024


def default_state_dir() -> Path:
    """Return AegisGraph-owned state storage, never the target repository."""

    override = os.environ.get("AEGISGRAPH_STATE_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return (Path.home() / "Library" / "Application Support" / "AegisGraph").resolve()
    if os.name == "nt":
        local_app_data = os.environ.get("LOCALAPPDATA")
        if local_app_data:
            return (Path(local_app_data) / "AegisGraph").resolve()
    xdg_state_home = os.environ.get("XDG_STATE_HOME")
    if xdg_state_home:
        return (Path(xdg_state_home).expanduser() / "aegisgraph").resolve()
    return (Path.home() / ".local" / "state" / "aegisgraph").resolve()


def default_audit_path() -> Path:
    return default_state_dir() / "aegis-invocations.jsonl"


def resolve_output_path(
    path: str | Path, *, target_root: str | Path | None = None
) -> Path:
    """Resolve an Aegis-owned output and reject writes inside a declared target."""

    output = Path(path).expanduser().resolve()
    if target_root is None:
        return output
    target = Path(target_root).expanduser().resolve()
    if output == target or output.is_relative_to(target):
        raise ValueError("AegisGraph output may not be written inside the target")
    return output


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

    def __post_init__(self) -> None:
        for label, value in (
            ("timestamp", self.timestamp),
            ("mode", self.mode),
            ("target", self.target),
            ("source", self.source),
            ("status", self.status),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"invocation {label} must be a non-empty string")
        if self.verdict not in {None, "pass", "fail", "unknown"}:
            raise ValueError(f"invalid invocation verdict: {self.verdict}")
        if self.duration_ms is not None and self.duration_ms < 0:
            raise ValueError("invocation duration_ms may not be negative")


def new_record(*, mode: str, target: str, source: str = "aegis", status: str = "completed", verdict: str | None = None, evidence_snapshot_id: str | None = None, target_commit: str | None = None, duration_ms: int | None = None, note: str | None = None) -> InvocationRecord:
    return InvocationRecord(
        timestamp=datetime.now(UTC).isoformat(),
        mode=mode,
        target=str(Path(target).expanduser().resolve()),
        source=source,
        status=status,
        verdict=verdict.lower() if verdict else None,
        evidence_snapshot_id=evidence_snapshot_id,
        target_commit=target_commit,
        duration_ms=duration_ms,
        note=note,
    )


def append_invocation(record: InvocationRecord, path: str | Path | None = None) -> Path:
    output = resolve_output_path(
        default_audit_path() if path is None else path,
        target_root=record.target,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    payload = (json.dumps(asdict(record), ensure_ascii=False, default=str) + "\n").encode("utf-8")
    if len(payload) > MAX_AUDIT_LINE_BYTES:
        raise ValueError(
            f"audit record exceeds {MAX_AUDIT_LINE_BYTES} byte limit"
        )
    flags = os.O_APPEND | os.O_CREAT | os.O_WRONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    descriptor = os.open(output, flags, 0o600)
    try:
        written = os.write(descriptor, payload)
        if written != len(payload):
            raise OSError(f"partial audit append: wrote {written} of {len(payload)} bytes")
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return output


def load_invocations(
    path: str | Path | None = None, *, limit: int | None = None
) -> tuple[InvocationRecord, ...]:
    source = default_audit_path() if path is None else Path(path).expanduser().resolve()
    if not source.exists():
        return ()
    records: list[InvocationRecord] | deque[InvocationRecord] = (
        [] if limit is None else deque(maxlen=max(0, limit))
    )
    malformed_rows = 0
    with source.open("rb") as handle:
        for raw in handle:
            if not raw.strip():
                continue
            if len(raw) > MAX_AUDIT_LINE_BYTES:
                malformed_rows += 1
                continue
            try:
                decoded = raw.decode("utf-8")
                records.append(InvocationRecord(**json.loads(decoded)))
            except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
                malformed_rows += 1
                continue
    if malformed_rows:
        warnings.warn(
            f"AegisGraph audit trail skipped {malformed_rows} malformed row(s) from {source}",
            RuntimeWarning,
            stacklevel=2,
        )
    return tuple(records)


def summarize_invocations(records: Iterable[InvocationRecord]) -> dict[str, object]:
    rows = tuple(records)
    verdict_counts: dict[str, int] = dict.fromkeys(("pass", "fail", "unknown"), 0)
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
