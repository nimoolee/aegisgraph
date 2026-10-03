# AegisGraph

> **Semantic verification for AI-generated code.**
>
> Catch architectural and behavioral drift even when the code compiles and tests pass.

**Every Change Needs Proof. / 每一次变更，都需要证明。**

[中文说明](README.zh-CN.md) · [Why AegisGraph?](docs/WHY_AEGISGRAPH.md) · [Contributing](CONTRIBUTING.md)

AegisGraph is an open-source **software change assurance** layer for teams using Claude Code, Codex, Cursor, Copilot, or any other coding agent. It sits beside your codebase, builds a semantic model from implementation evidence, evaluates explicit invariants, and produces an explainable **Change Proof** instead of trusting “tests are green” as the whole definition of correctness.

AegisGraph is **not another coding agent**. It does not decide your architecture and it does not modify the target repository. Its job is narrower and more useful: **Define → Observe → Judge → Prove.**

## Why this exists

AI coding agents are getting better at producing code, but large projects still fail in a different way:

- a change works locally but violates an architectural decision;
- a new session re-implements something that already exists;
- tests pass while a business invariant is silently broken;
- code review cannot see the full semantic blast radius;
- the agent “fixes” the implementation by weakening the guardrail itself.

AegisGraph treats those as a verification problem, not a prompting problem.

```text
Code / Git Worktree
        ↓
Semantic Discovery
        ↓
Semantic Unification
        ↓
Conflict Detection
        ↓
Accepted Facts / Rules / Invariants
        ↓
Change Impact + Evidence
        ↓
PASS / FAIL / UNKNOWN
        ↓
Change Proof + Repair Contract
```

## 5-minute quick start

AegisGraph v1.0 has no runtime third-party dependencies and requires Python 3.11+.

Fastest install directly from GitHub:

```bash
python3 -m pip install "git+https://github.com/nimoolee/aegisgraph.git@v1.0.0"
aegis demo
```

For contributors who want an editable checkout:

```bash
git clone https://github.com/nimoolee/aegisgraph.git
cd aegisgraph
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
```

Run the dependency-free proof demo:

```bash
aegis demo
```

You will see a deliberately broken architecture rule fail first, followed by the repaired implementation passing:

```text
1) Broken implementation -> FAIL
2) Repaired implementation -> PASS
```

Discover candidate semantics in any Python codebase:

```bash
aegis discover /path/to/your/project --conflicts
```

Use conservative conflict detection as a CI gate:

```bash
aegis check /path/to/your/project
```

`aegis check` exits non-zero only when AegisGraph finds a high-confidence semantic conflict. Scope ambiguity is retained as evidence instead of being forced into a fake answer.

## What v1.0 actually supports

- **Python Semantic Discovery** — concepts, formulas, relationships, functions, calls, source anchors, and code context.
- **Semantic Unification** — conservative alias/entity unification without merging unrelated locals merely because names match.
- **Conflict Detection** — incompatible candidate definitions with provenance.
- **Software Graph** — Facts, Relationships, Rules, Contexts, and Invariants.
- **Change Impact / Blast Radius** — bounded multi-path impact analysis.
- **Executable Invariants** — deterministic validators return PASS / FAIL / UNKNOWN.
- **Change Proof** — explainable result envelope with affected invariants and evidence.
- **Repair Contract** — implementation-neutral constraints describing what must change, what must be preserved, and what evidence must be re-verified.
- **Semantic Change Management** — versioned candidate/accepted rule evolution.
- **REG Dashboard** — read-only semantic graph, current verdicts, impact, and invocation audit for integrations.

Current limitations are deliberate: generic discovery is Python-first, and project-specific accepted invariants still need an integration/adapter. AegisGraph does not pretend discovered candidates are automatically business truth.

## The key difference

Traditional tests ask:

> “Did this code produce the expected output for these examples?”

AegisGraph additionally asks:

> “What did this change affect, what must still remain true, and do we have evidence for it?”

That distinction matters when an AI agent writes code that is syntactically correct, test-passing, and semantically wrong.

## Example: a test-passing architecture regression

Imagine your approved rule is:

```text
Refunds must go through PaymentGateway.
```

An agent later writes a direct provider call. The endpoint works. Existing tests may still pass. AegisGraph can model the invariant independently and return:

```text
FAIL payments.inv.refunds_use_gateway

Repair Contract
- Must change: restore routing through the approved gateway
- Must preserve: externally visible refund behavior
- Must not change: do not weaken the invariant to manufacture PASS
- Required verification: re-run the refund-path invariant
```

Run the exact public demo with `aegis demo`.

## REG — the semantic map

AegisGraph includes a read-only REG (Relationship / Evidence / Graph) interface used to inspect Fact / Rule / Invariant / Context relationships, current PASS / FAIL / UNKNOWN status, impact paths, and AegisGraph's own invocation history.

The current REG examples are integration-specific while the core graph engine stays domain-agnostic.

## Product boundary

- Target repositories are read-only during discovery and verification.
- AegisGraph is a sidecar/observer, not a runtime dependency of the product being verified.
- Core contains no trading-, payment-, or vendor-specific business truth.
- Integrations provide domain evidence and accepted invariants without contaminating Core.
- AegisGraph does not prescribe target architecture or implementation details.
- Repair Contracts are verification contracts, not generated patches.
- Missing evidence is `UNKNOWN`, never silently converted to `PASS`.

## Use with coding agents

AegisGraph is model-agnostic. A practical workflow is:

```text
Developer / Architect defines intent
        ↓
Claude Code / Codex / Cursor implements
        ↓
AegisGraph discovers + audits
        ↓
PASS → merge
FAIL → Repair Contract → implementation agent
UNKNOWN → collect missing evidence
```

This separation is intentional: the same agent that wrote a change should not be the only authority deciding whether the change is semantically correct.

## Development

```bash
python -m pip install -e '.[dev]'
pytest -q
```

The repository also contains reference integrations and historical development notes under `docs/` and `examples/`. They are evidence that Core works on real systems, not dependencies of the generic engine.

## Roadmap

Near-term priorities after v1.0:

- generic Git diff → semantic change mapping;
- first-class replay/evidence adapters;
- additional language frontends;
- CI-native proof artifacts;
- reusable integration SDK and starter templates;
- REG packaging that is fully generic rather than reference-integration specific.

## License

Apache License 2.0. See [LICENSE](LICENSE).

If AegisGraph catches one bug your tests missed, open an issue and tell us the invariant. Those real failure modes are the roadmap.
