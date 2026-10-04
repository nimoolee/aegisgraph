# Semantic Discovery v0.1

## Product shift

AegisGraph must not require a customer to hand-author a complete Constitution before it can be useful.
The product predefines the **language of software semantics** (concepts, formulas, relationships, states,
contexts, invariants, evidence, conflicts), not the business answers for a target system.

The existing `integrations/auto_trading.py` semantics are retained as a **Benchmark / Reference Answer**.
They are not inputs to discovery.

## Living Software Model states

Discovered semantic statements can be:

- `DISCOVERED` — observed in implementation evidence.
- `CANDIDATE` — evidence supports a possible semantic statement.
- `ACCEPTED` — accepted current system semantics (future unification/approval layer).
- `CONFLICTED` — same concept/context/version has incompatible definitions.
- `UNDEFINED` — the product/business meaning has not been decided.
- `UNIMPLEMENTED` — intended semantics exist but implementation does not.
- `UNKNOWN` — semantics are defined but evidence is insufficient to prove reality.

`UNDEFINED`, `UNIMPLEMENTED`, and `UNKNOWN` are intentionally different.

## v0.1 scope

Semantic Discovery v0.1 is intentionally small:

1. Read a Python target **without modifying it**.
2. Prefer the current Git worktree as the source-code boundary. Ignored runtime snapshots/backups are not
   treated as current implementation semantics.
3. Extract code-level candidate concepts from assignments and keyed state reads.
4. Extract candidate formulas using Python AST expressions.
5. Preserve file, line, function, and enclosing conditional context for every formula.
6. Emit candidate `derived_from` relationships from formula inputs to outputs.
7. Treat tests as supporting evidence and exclude them from default definition discovery.

It does **not** yet:

- decide the business name of a discovered concept;
- unify aliases across modules;
- choose one formula as authoritative truth;
- automatically generate invariants;
- classify formula differences as conflicts versus legitimate context/version variants;
- build the final visual graph UI.

Those are later stages.

## First blind benchmark

The first benchmark target is a reference auto-trading system, but the discovery engine contains no
project-specific account labels, venue names, strategy names, or private repository vocabulary.

Success means the generic extractor can independently recover implementation structure such as:

```text
trade_ledger + cash
        ↓
physical_headroom = min(max(0, trade_ledger), cash)
        ↓
orderable = threshold(physical_headroom)
        ↓
orderable_balance
```

and retain the context in which that formula applies, for example `RISK_MODE == 'SAFE_TRADE'`.
Only after discovery do we compare its output with the hidden human-authored benchmark.
