# Changelog

All notable changes to AegisGraph are documented here.

## 1.0.1 — 2026-10-04

Audited v1.0 hardening release. No new product features.

### Fixed

- Enforce fail-closed PASS / FAIL / UNKNOWN behavior when source or runtime evidence is incomplete or malformed.
- Remove depth-truncation risk from semantic impact reachability and require exact invariant-check coverage in proofs.
- Make accepted semantic, discovery, impact, governance, and proof value objects resistant to caller-side mutable aliasing.
- Enforce the read-only target boundary for CLI audit state and official REG report outputs.
- Harden portable REG HTML against script/DOM injection through untrusted graph or invocation data.
- Stream and content-hash runtime evidence with bounded input sizes and explicit snapshot-integrity warnings.
- Add locked, reproducible CI quality gates for Ruff, mypy strict, Bandit, package build, and Twine validation.
- Sanitize private benchmark repository paths, commit identifiers, and incident references from the public source tree.

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
