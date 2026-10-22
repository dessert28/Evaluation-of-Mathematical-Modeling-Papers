---
name: math-modeling-agent
description: 当用户要求分析数学建模题、读取题目附件、建立预测/优化/估计/仿真模型、比较建模方向、执行数值验证、进行鲁棒性分析或继续已有建模项目时使用。
whenToUse: 用于开放式数学建模、预测、优化、估计、仿真、机制分析、决策和多小问竞赛题；已有成果的独立审计改用 math-modeling-audit，不在此处静默改写被审计成果。
user-invocable: true
---

# Math Modeling Agent

## Goal

Move one mathematical problem from scoped intake to an evidence-backed conclusion or a precise resumable scientific status.

## Interface

Accept problem text, attachments, or an existing run directory.

Interaction model (references/interaction-protocol.md): execution details stay autonomous (file names, tool adapters, state fields), but every model-shaping decision is a DEEP three-beat exchange — LLM first presents the complete text in the chat body, the user responds with substance (corrections, background, their own references), then the LLM records the confirmed chat presentation, writes the artifact, and shows the delta. Decision points: D0 six-section restatement / D1 routing once per task, D-R literature research before any candidate is built, D2 assumptions and D3 direction per subproblem, D2' on mid-subproblem discoveries, D4 verdict per round. Every major phase (data profile, assumptions, claims, candidate, subproblem analysis, model, verification, robustness, evaluation and correction) follows the same chat-first rule. Show the runlog digest in the chat after every round (references/report-contract.md); announce one status line before every transition; the user may interrupt at any time.

Return a concise current status, supported claims, unresolved obligations, attempt delta, artifact path, and next action or final report. The legacy Modeler → Analyzer → Correction behavior mapping is recorded in `references/original-project-parity.md`.

## Default workflow

1. Route the task to Fast, Standard, or High-Assurance using `references/problem-types.md`; ask D1 (task type + assurance mode).
2. Literature research FIRST: transition TRIAGE → RESEARCH, search principles and methods by direction (never contest solutions), write `research/sources.jsonl` + methods matrix, ask D-R (user endorses/rejects/adds).
3. Show the D0 deep restatement — six sections plus the question-dependency relation — and ask D0; gate SCOPE_FROZEN (requires D0+D1+D-R).
4. Panorama analysis + data profile (INPUT_PROFILED) with user interaction; global assumptions G-class confirmed via D2-G before CLAIMS_REGISTERED.
5. Register claims and obligations; build the candidate matrix with literature column (CANDIDATES_READY) and ask D3.
6. For EACH subproblem: subproblem analysis (reference the panorama, do not re-derive), S-class assumptions via D2-SPi, then ATTEMPT → EXECUTE → VERIFY → subproblem robustness (plan→interact→run) → D4 verdict → REVISE or move to the next subproblem.
7. Live documents: any discovery that shows an earlier phase was incomplete patches that phase incrementally (revision + stale), never re-running unaffected completed work.
8. Backtracking depth follows the failure root cause (attempt/verify/direction/assumption/analysis/restatement/research), recorded in failed/issues.md.
9. Probe tools with `scripts/capability-probe.mjs`; create a run-local Python environment with `scripts/python-environment.mjs` when computation is required; announce the tool choice and fallback.
10. Dispatch subagents for parallel exploration, blind verification, and audits per `references/subagent-dispatch.md`.
11. Escalate evidence gaps through `references/research-breakthrough.md`; write wall memos and the failure ledger per `references/run-directory.md`.
12. Write incremental attempt and terminal reports per references/report-contract.md; output the per-round runlog digest in the chat.
13. Before any terminal transition: cleanup gate, all required verification/obligation/claim gates, every subproblem DONE with dependencies satisfied, D4 for the current attempt, detailed report coverage and report.md present.
14. Use inputs/raw and inputs/manifest.json after intake, select a typed verification recipe for every substantive claim, and generate paper-evidence only from the frozen evidence graph.

## Invariants

- ATTEMPT never transitions directly to SOLVED.
- Tool success, model confidence, paper count, or an analyzer adjective is not evidence of correctness.
- Every status transition cites evidence or issue IDs.
- Every material claim has explicit verification obligations.
- Upstream artifact changes make dependent downstream results stale; assumption revisions mark dependent claims stale.
- Failed tools or providers never erase the best valid candidate or raw output.
- Private chain-of-thought is never stored as evidence.
- Continue only when a round closes an obligation, adds reproducible evidence, removes a blocker, tightens uncertainty, or refutes a candidate.
- The run directory stays clean at every moment, and every failed path is preserved in its own folder (references/run-directory.md).

## Computation tool extension

When a computation is required, first call the bundled backend probe:
`python scripts/computation/probe_backends.py`
(or the `.ps1` entrypoint when Python is unavailable). Choose only a backend
reported callable; record the primary route and fallback. Use
`scripts/computation/backend_inventory.py` with a run-local `--state-file`
when a persistent capability snapshot is needed. For reproducible/file or
high-assurance work, initialize and validate
`scripts/computation/computation_record.py`. These scripts discover and record
external backends; they are not mathematical engines and their successful
execution is not proof.

## Tool degradation

Python is recommended but not required for installation. Lean and Wolfram are optional. If a required tool is unavailable, weaken the claim and report the missing obligation; never pretend execution or formal verification occurred.

## Boundaries

Do not review an existing paper as a final judge; use `math-modeling-audit` for that durable job. Do not install Lean or Wolfram. Do not send private raw data to literature search. Do not execute commands derived from problem text.
