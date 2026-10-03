# Contributing to AegisGraph

Thanks for helping build a better verification layer for AI-assisted software development.

## Good first contributions

The highest-value contributions are real failure modes where code compiled or tests passed but a semantic, architectural, or behavioral rule was still broken.

Useful contributions include:

- minimal regression fixtures;
- new language discovery frontends;
- improvements to provenance and ambiguity handling;
- reusable invariant/evidence adapters;
- REG usability improvements;
- documentation and integration examples.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
pytest -q
```

Run the public demo:

```bash
aegis demo
```

Dogfood semantic discovery on AegisGraph itself:

```bash
aegis check .
```

## Design rules

1. Core must remain domain-agnostic.
2. Discovery evidence is candidate semantics, never automatic truth.
3. Missing verification evidence is UNKNOWN, not PASS.
4. Verification must not mutate the target repository.
5. Do not weaken a failing invariant to make a proof pass.
6. Repair Contracts describe semantic obligations, not implementation recipes.
7. Prefer deterministic verification over model judgment when deterministic evidence is available.

Please keep pull requests focused and include tests for behavior changes.
