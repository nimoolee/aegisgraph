"""Machine-executable invariant verification for AegisGraph v1.0."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from aegis_graph.graph.store import SoftwareGraph


class InvariantStatus(str, Enum):
    # This is a verifier verdict string, never credential material.
    PASS = "pass"  # nosec B105
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InvariantCheck:
    invariant_id: str
    status: InvariantStatus
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.invariant_id, str) or not self.invariant_id.strip():
            raise ValueError("invariant check id must be a non-empty string")
        if not isinstance(self.status, InvariantStatus):
            raise TypeError("invariant check status must be InvariantStatus")
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("invariant check message must be a non-empty string")


ValidatorReturn = bool | tuple[bool, str]
InvariantValidator = Callable[[Mapping[str, Any]], ValidatorReturn]


class InvariantExecutor:
    """Executes only the invariants selected by semantic impact analysis.

    Validators are registered outside the generic graph model. This keeps authored
    semantic truth separate from executable verification code and lets integrations
    provide domain-specific checks without leaking them into AegisGraph Core.
    """

    def __init__(self, graph: SoftwareGraph) -> None:
        self.graph = graph
        self._validators: dict[str, InvariantValidator] = {}

    def register(self, invariant_id: str, validator: InvariantValidator) -> None:
        if invariant_id not in self.graph.invariants:
            raise ValueError(f"unknown invariant id: {invariant_id}")
        self._validators[invariant_id] = validator

    def verify(
        self,
        invariant_ids: tuple[str, ...],
        fact_values: Mapping[str, Any] | None = None,
    ) -> tuple[InvariantCheck, ...]:
        values = fact_values or {}
        checks: list[InvariantCheck] = []

        for invariant_id in sorted(invariant_ids):
            invariant = self.graph.invariants[invariant_id]
            validator = self._validators.get(invariant_id)
            if validator is None:
                checks.append(
                    InvariantCheck(
                        invariant_id=invariant_id,
                        status=InvariantStatus.UNKNOWN,
                        message="no executable validator registered",
                    )
                )
                continue

            missing = sorted(fact_id for fact_id in invariant.facts if fact_id not in values)
            if missing:
                checks.append(
                    InvariantCheck(
                        invariant_id=invariant_id,
                        status=InvariantStatus.UNKNOWN,
                        message=f"missing evidence for facts: {', '.join(missing)}",
                    )
                )
                continue

            evidence = {fact_id: values[fact_id] for fact_id in invariant.facts}
            try:
                outcome = validator(evidence)
                if isinstance(outcome, bool):
                    passed = outcome
                    message = "invariant satisfied" if passed else "invariant violated"
                elif (
                    isinstance(outcome, tuple)
                    and len(outcome) == 2
                    and isinstance(outcome[0], bool)
                    and isinstance(outcome[1], str)
                    and bool(outcome[1].strip())
                ):
                    passed, message = outcome
                else:
                    raise TypeError(
                        "validator must return bool or exactly tuple[bool, str]"
                    )
            except Exception as exc:
                # Fail closed: validator bugs and contract violations are UNKNOWN, never PASS.
                checks.append(
                    InvariantCheck(
                        invariant_id=invariant_id,
                        status=InvariantStatus.UNKNOWN,
                        message=f"validator error: {type(exc).__name__}: {exc}",
                    )
                )
                continue

            checks.append(
                InvariantCheck(
                    invariant_id=invariant_id,
                    status=InvariantStatus.PASS if passed else InvariantStatus.FAIL,
                    message=message,
                )
            )

        return tuple(checks)
