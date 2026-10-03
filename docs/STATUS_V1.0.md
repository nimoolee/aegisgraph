# AegisGraph v1.0 Status

Released: 2026-10-03

## Release definition

AegisGraph v1.0 is the first public product release. It is intentionally narrower than a general-purpose AI code reviewer: it provides a deterministic, explainable semantic-verification core and a Python-first discovery frontend.

## Public product surface

- `aegis demo` — zero-configuration invariant proof demonstration.
- `aegis discover <target>` — read-only Python semantic discovery + unification.
- `aegis check <target>` — CI-friendly conservative semantic conflict gate.
- Python API — SoftwareGraph, AegisEngine, executable invariants, Change Proof and Repair Contract.
- REG foundations — read-only relationship/evidence graph and invocation audit used by reference integrations.

## 1.0 guarantees

- Target discovery/verification is read-only.
- Missing evidence is UNKNOWN, never implicit PASS.
- Discovered candidates are not automatically accepted business truth.
- Failed invariants cannot be disabled or weakened as a valid repair.
- Repair Contracts remain implementation-neutral.
- Core remains domain-agnostic; business semantics live in integrations.

## Release validation

The v1.0 release gate includes:

- full pytest suite;
- clean install into a fresh Python 3.12 virtual environment;
- `aegis demo` FAIL → PASS proof flow;
- `aegis check .` dogfood semantic scan;
- package metadata/version consistency.

## Post-1.0 priorities

1. Generic Git diff → semantic change mapping.
2. First-class replay/evidence adapter API.
3. Additional language frontends.
4. CI proof artifacts and annotations.
5. Generic REG packaging.
6. Integration SDK/templates for project-specific accepted invariants.
