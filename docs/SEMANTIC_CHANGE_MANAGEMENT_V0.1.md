# Semantic Change Management v0.1

## Goal

AegisGraph must not solve code drift by silently changing the rules that judge the code.
This layer makes semantic truth itself versioned, reviewable, impact-aware, and explicitly approved.

## Lifecycle

```text
Discovered / Human Decision
        ↓
Candidate Semantic Rule vN
        ↓
Semantic Diff
        ↓
Rule Impact Analysis
        ↓
APPROVAL_REQUIRED
        ↓ explicit approval of this exact version
Accepted Semantic Rule vN
        ↓
Target implementation may change
        ↓
Change Proof / Re-verification
```

A candidate is never automatically promoted because it appears frequently in code or because
accepting it would make a failing system pass.

## v0.1 guarantees

- Rule content is append-only and versioned. Older accepted versions remain available in history.
- Pre-existing accepted graph rules/invariants are migrated as a baseline version; migration does not invent a new business decision, and subsequent changes start at the next version.
- Acceptance is a separate explicit approval record tied to one exact semantic id + version.
- A semantic diff identifies changed fields such as formula, applicability, facts, inputs, outputs, or context.
- Rule changes run through the existing `ImpactAnalyzer` before implementation changes are made.
- A Rule Change Proof returns `APPROVAL_REQUIRED`, `ACCEPTED`, or `NO_CHANGE`.
- Affected invariants become Required Verification obligations.
- The current accepted graph is updated only after approval, using compare-and-swap version guards.
- A Developer AI cannot turn a candidate into accepted truth merely by changing target code.
- Target systems remain read-only to AegisGraph.

## Important distinction

Changing implementation to satisfy an accepted invariant is a **Code Change**.
Changing the accepted invariant itself is a **Semantic Change** and requires its own approval/proof gate.

This prevents the failure mode:

```text
code fails invariant
→ weaken invariant
→ tests become green
```

Instead:

```text
code fails invariant
→ invariant stays fixed
→ Repair Contract constrains implementation repair
```

If product intent truly changes, a new rule version is proposed, diffed, impact-analyzed, approved, then installed.

## v0.1 non-goals

- no target-code patch generation;
- no autonomous approval of product semantics;
- no UI approval workflow yet;
- no persistent database/event store yet (the lifecycle API is append-only in memory in v0.1);
- no automatic claim that a discovered formula is business truth.
