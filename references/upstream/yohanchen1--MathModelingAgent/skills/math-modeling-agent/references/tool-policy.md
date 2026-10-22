# Tool Policy

## Capability discovery

Run `scripts/capability-probe.mjs`; treat PATH hits as candidates, then verify version and usability through the available DSH shell. Record unavailable, candidate, available, or unknown with reason.

## Long-running commands (stall governance, v2)

- Estimate BEFORE starting: anything expected > 60 s MUST run in the background
  (run_in_background), and the chat gets one line immediately: what runs, the
  estimate, and what independent work continues in parallel. Never idle-wait.
- Tasks running > 3 minutes get a proactive progress check (job_output) with a
  one-line progress report to the chat.
- Expensive computations are benchmarked on a small subset first (e.g. 20-node
  trial) to calibrate the full-run estimate.
- On job completion, report the outcome within the same round.

## Tool selection visibility (v2)

At the start of every phase, say ONE line about the tool choice and why:
e.g. "本阶段用 Python+OSQP 做约束优化；Wolfram 对本题非必需，跳过；Lean 不适用".
The problem never silently depends on a single tool: every phase names its
backend, its fallback, and the degradation path when the backend fails.

## Computation backend extension

Before selecting an external computation backend, run
`scripts/computation/probe_backends.py` (or its PowerShell compatibility entry)
and use only the live capability result. Persist a backend snapshot with
`scripts/computation/backend_inventory.py` and an explicit run-local
`--state-file` when the phase needs a stable inventory. Use
`scripts/computation/computation_record.py` for reproducible/file or
high-assurance computation. A probe, inventory, or record validation does not
prove a mathematical claim.

## Python

Use `scripts/python-environment.mjs`. Prefer uv, then an existing Python runtime plus venv. Keep the environment under the run directory. Install only required normalized PyPI package names; VCS URLs, local wheels, or arbitrary indexes require explicit user approval. Record lock, seed, command, workdir, timeout, stdout/stderr, exit code, and generated files.

## Lean

Never auto-install. Use only for formalizable obligations. Record Lean/Lake/library versions, axioms/imports, proof artifact, absence of sorry/admit, and a separate natural-language-to-formal-statement fidelity check.

## Wolfram

Never auto-install. Verify executable and license usability. Use for applicable symbolic, exact, or high-precision claims and state the exact coverage boundary.

## Search, PDF, and images

Use available web, PDF, vision/OCR, or local Python readers. Do not send private raw data in search queries. Missing capabilities lower evidence level rather than causing fabricated execution.
