# AegisGraph v0.1 Status

Updated: 2026-10-03

## Current state

AegisGraph has moved beyond a skeleton. The first end-to-end semantic verification slice is working:

```text
Change
  -> semantic seeds
  -> typed relationship/rule propagation
  -> bounded multi-path blast radius
  -> affected invariants
  -> executable invariant checks
  -> PASS / FAIL / UNKNOWN Change Proof
```

## Milestones

- M0 Skeleton: COMPLETE
- M1 Graph Core: COMPLETE for v0.1 scope
- M2 Change + Impact: COMPLETE for manually mapped semantic changes
- M3 Verification: COMPLETE for callable invariant validators; test/replay hooks remain next
- M4 Trading V2.1 first integration: COMPLETE for the CLOB-first execution-balance -> BUY UI slice
- M5 Auto Trading first integration: PARTIAL; cash/orderability/signal-decision and manual-position independence are integrated, Temporal Rules remain next
- M6 First Real Proof: PARTIAL; real source relationships are integrated and synthetic evidence produces deterministic proofs, but real Git-diff mapping + runtime/history Replay are not yet connected

## Reference integration 1 — Trading V2.1

Reference commit: `785b6863953ff9e3f08e04cfdfd2383ce5cb3923`

First slice:

```text
CLOB Available Balance
  -> Execution Balance
  -> Account Snapshot Execution Balance
  -> Manual BUY Eligibility
  -> UI BUY Button
```

The integration is anchored to real source locations in the reference repository. It verifies:

1. Execution Balance remains CLOB-first.
2. Manual BUY eligibility matches balance and execution-readiness inputs.
3. The UI BUY button matches the semantic eligibility result.

## Reference integration 2 — Auto Trading

Reference commit: `545b0a319e7a9993cf96368f35184a59f5d28964`

First slice:

```text
Trading Cash ----\
                  -> Orderable Cash -> Signal Execution Decision
CLOB Free Cash --/
```

A real integration finding required a new generic semantic relationship:

`INDEPENDENT_OF`

This captures constraints such as:

```text
Manual Position INDEPENDENT_OF Automatic Entry Decision
```

It does not propagate impact as a causal dependency. Instead, modifications to the independent fact select the relevant invariant, which can prove that the forbidden coupling has not appeared.

## Important product learning

A single affected fact can be reachable by more than one valid semantic path. AegisGraph therefore retains bounded alternate Impact Paths rather than flattening the graph to one first-found path.

Example from Auto Trading:

```text
Trading Cash -> Orderable Cash -> Signal Decision
Trading Cash --------------------> Signal Decision
```

Both are real: Trading Cash affects orderability and is also read directly for explicit low-cash failure attribution.

v0.1 currently bounds path exploration to prevent graph explosion.

## Next development target

Do not add more visualization or platform infrastructure yet.

Next target:

1. Git Diff -> semantic mapping for the two reference systems.
2. Replay Evidence interface.
3. Auto Trading Temporal Context / Temporal Rule integration.
4. First proof generated from a real historical change and real recorded evidence.

That is the point at which AegisGraph starts protecting ongoing development rather than only modeling it.
