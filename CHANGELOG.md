# Changelog

All notable changes to AegisGraph are documented here.

## 1.0.0 — 2026-10-03

First public product release.

### Added

- Python semantic discovery with implementation provenance.
- Conservative semantic unification and conflict detection.
- Generic Fact / Relationship / Rule / Context / Invariant graph model.
- Multi-path change impact analysis.
- Executable invariant verification with PASS / FAIL / UNKNOWN proofs.
- Implementation-neutral Repair Contracts.
- Semantic rule change management.
- REG graph/dashboard and invocation audit foundations.
- `aegis` CLI with `demo`, `discover`, and CI-friendly `check` commands.
- Public generic architecture-regression demo.
- Real-system reference integrations used as verification benchmarks.

### Product guarantees

- Read-only target boundary for discovery and verification.
- Missing evidence never silently becomes PASS.
- Candidate discovery is not automatically promoted to accepted business truth.
- Verification contracts do not prescribe target implementation architecture.
