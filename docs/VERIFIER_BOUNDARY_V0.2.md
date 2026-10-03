# Verifier Boundary v0.2

AegisGraph is a semantic verification system, not a coding agent or architecture agent.

## What Aegis may do

Aegis may describe:

- what the target software is expected to mean;
- what evidence shows it currently does;
- semantic contradictions and violated invariants;
- structural evidence and structural risk, such as multiple writers, circular state dependencies, ambiguous ownership, or duplicated attribution;
- semantic blast radius;
- what must become true;
- what must remain true;
- what evidence and invariants must be re-verified after a change.

## What Aegis must not do

Aegis must not prescribe:

- a target-system architecture or re-architecture;
- refactors as the required remedy;
- services, modules, classes, functions, data structures, queues, databases, or frameworks to introduce;
- which source file or function a developer should rewrite;
- concrete patches, pseudocode patches, implementation sequences, or coding instructions.

If evidence indicates a structural problem, Aegis reports `STRUCTURAL RISK` with the supporting facts and relationships, then stops at the implementation boundary. The Developer AI / Architect decides how to satisfy the verification constraints.

Naming the evidence location (for example, a source anchor) is allowed for traceability. Recommending that the developer rewrite that location is not.

## Repair Contract meaning

The existing `RepairContract` name is retained for API compatibility. Its content is a Verification Contract, not a repair design.

It contains only:

- Must Change: semantic outcomes that must become true;
- Must Preserve: accepted semantics that must remain true;
- Must Not Change: forbidden semantic regressions;
- Required Verification: invariants or behaviors that must be re-proved;
- Required Evidence: evidence needed for that proof.

It must remain implementation-neutral.

This boundary also applies to user-facing diagnosis text: Aegis may name the semantic concept or evidence anchor involved, but it must not turn that into a prescribed architecture or implementation plan.

> AegisGraph may describe what is wrong, what must become true, and what must remain true. It must not prescribe how the target should be implemented.
