# Why AegisGraph exists

AI coding has shifted the bottleneck from code generation to change assurance.

Modern agents can generate large changes quickly. The difficult failures are increasingly semantic: code compiles, tests pass, and the implementation still violates a decision the system was supposed to preserve.

AegisGraph focuses on four recurring failure modes:

1. **Architecture drift** — an agent bypasses an approved boundary because the local implementation looks simpler.
2. **Semantic regression** — a business invariant changes while the existing test examples remain green.
3. **Context drift** — a later session no longer carries the reasoning that made an earlier constraint important.
4. **Self-certification** — the implementation agent also edits the test, fallback, or rule that judges its own work.

Prompts, memory files, RAG, and AGENTS.md help an agent *know* a rule. They do not independently prove that a concrete change still obeys it.

AegisGraph therefore separates the roles:

```text
Implementation agent  -> writes or refactors code
AegisGraph             -> observes evidence and verifies semantics
Developer/Architect    -> owns intent and accepted rules
```

The product deliberately fails closed:

- missing evidence is UNKNOWN;
- candidate semantics are not accepted truth;
- target repositories stay read-only during verification;
- a failed invariant cannot be weakened to manufacture PASS;
- Repair Contracts describe semantic obligations, not architecture prescriptions.

This makes AegisGraph complementary to tests, static analysis, linters, code review, and AI coding agents rather than a replacement for any of them.
