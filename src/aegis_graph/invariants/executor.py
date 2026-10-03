"""Machine-executable invariant verification for AegisGraph v0.1."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from enum import Enum
from typing import Any

from aegis_graph.graph.store import SoftwareGraph


class InvariantStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class InvariantCheck:
    invariant_id: str
    status: InvariantStatus
    message: str


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
            except Exception as exc:  # fail closed: verifier bugs are not PASS
                checks.append(
                    InvariantCheck(
                        invariant_id=invariant_id,
                        status=InvariantStatus.UNKNOWN,
                        message=f"validator error: {type(exc).__name__}: {exc}",
                    )
                )
                continue

            if isinstance(outcome, tuple):
                passed, message = outcome
            else:
                passed = outcome
                message = "invariant satisfied" if passed else "invariant violated"

            checks.append(
                InvariantCheck(
                    invariant_id=invariant_id,
                    status=InvariantStatus.PASS if passed else InvariantStatus.FAIL,
                    message=message,
                )
            )

        return tuple(checks)
