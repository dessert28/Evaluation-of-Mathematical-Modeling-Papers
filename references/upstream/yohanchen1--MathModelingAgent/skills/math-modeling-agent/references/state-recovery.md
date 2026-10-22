# State and Recovery

Default run root: `math-modeling-runs/<task-id>/`.

Required durable files:

- run.json: atomic current snapshot;
- ledger.json: scope, assumptions, claims, obligations, subproblems, candidates, and issues;
- events.jsonl: append-only transition journal;
- problem-brief.md and inputs.json;
- attempts/<number>/report.md plus code/artifacts only when they exist;
- research/sources.jsonl and methods.md only when research occurs;
- walls/ only when a direction is abandoned;
- reproducibility.json and final-report.md for terminal output.

Use `scripts/run-state.mjs` for initialization, transition, validation, and recovery. A transition without evidence/issue references is invalid. Provider, parser, or verifier failure preserves raw output and the best candidate. Resume by validating state, recovering from the last journal snapshot when needed, then skipping hash-stable completed work.

Failure classes include data missing/schema/leakage, tool unavailable/dependency/license, runtime/timeout/numerical instability, model/assumption/parameter, verification/formalization, citation/research, parser/provider, no progress, and budget exhausted.
