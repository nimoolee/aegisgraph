# Semantic Unification v0.1

## Goal

Turn code-level discoveries into a conservative candidate software-world model without requiring an authored business Constitution.

This stage does **not** decide business truth. It only establishes stronger candidate identity and data-flow evidence so later verification can distinguish real semantic conflicts from normal implementation variation.

## What v0.1 does

1. Keeps bare local variables scoped by `file + function + symbol` so the same variable name in unrelated functions is not merged by name alone.
2. Treats stable keyed state such as `state["..."]` as process-wide implementation identity, while `self.<field>` is scoped to `file + owning class + field` so unrelated classes do not collapse into one concept.
3. Collapses only strongly evidenced aliases/projections, including direct assignment, representation conversion, keyed storage reads, and selected normalization wrappers.
4. Preserves formulas, source anchors, conditional contexts, confidence, and alias evidence.
5. Discovers interprocedural function-call flow for unambiguous local functions. A direct caller argument is connected to the callee parameter with a `parameter_from` relationship rather than blindly unioning both concepts.
6. Detects candidate semantic conflicts only after prior semantic unification has established that independent implementation scopes refer to the same candidate concept.
7. Excludes mutable storage transitions, including persisted state keys and class-owned `self.<field>` updates, plus ordinary alias/projection formulas from v0.1 conflict claims.

## Conservative design rule

AegisGraph prefers **UNKNOWN / separate candidates** over a false merge.

Two symbols are not the same business concept merely because they share a name. Two formulas are not conflicting merely because they produce fields with the same key. Different contexts, state transitions, try/except branches, and independent return schemas must not be collapsed into false contradictions.

## Interprocedural flow

For a pattern such as:

```python
observed = normalize(state.get("account_balance"))
result = helper(observed)

def helper(cash):
    gap = cash - other
```

v0.1 can preserve the evidence chain:

```text
state["account_balance"]
    ↕ alias/projection
observed
    ← parameter_from →
helper.cash
    ↓ derived_from
gap
```

The call edge is a relationship, not automatic concept identity. A generic helper may receive semantically different values at different call sites.

## Conflict rule in v0.1

A candidate conflict requires all of the following:

- the output has already been unified into one candidate semantic concept;
- formulas apply in the same discovered context;
- formulas are non-alias candidate definitions;
- the definitions come from independent implementation scopes;
- the output is not simply mutable persisted state being changed over time.

If these conditions are not satisfied, v0.1 does not claim a semantic conflict.

## Explicit limitations

v0.1 does not yet:

- assign authoritative business names;
- decide which candidate definition is correct;
- infer product intent from code alone;
- model arbitrary dynamic dispatch, higher-order calls, decorators, reflection, or cross-language call graphs;
- treat Git history as a full semantic-version graph;
- generate the final visual knowledge-graph UI;
- promote discovered candidates to `ACCEPTED` without a separate acceptance/evidence process.

## Completion criterion

This stage is considered complete when the AegisGraph unit suite proves:

- stable-storage projection unification;
- scope-safe local identity;
- context separation;
- conservative conflict behavior;
- no false conflict from identical return-key names;
- no false merge for identical `self.<field>` names owned by different classes;
- no false conflict from initialization/refresh updates to mutable object state;
- interprocedural parameter flow from caller facts into helper formulas.
