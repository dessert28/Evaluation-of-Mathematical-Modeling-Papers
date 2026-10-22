# Modeling Workflow

## Modes

- Fast: explicit low-risk calculation; at most two clarifications; direct inverse, substitution, domain, or unit check.
- Standard: normal modeling; input profile, baseline, candidates, execution, sensitivity, and reproducibility.
- High-Assurance: publication, proof, global optimum, causal, safety, guarantee, or high-stakes use; require independent audit.

## States

TRIAGE → RESEARCH → SCOPE_FROZEN → INPUT_PROFILED → CLAIMS_REGISTERED → CANDIDATES_READY → ATTEMPT → EXECUTE → VERIFY.

VERIFY may move to REVISE, RESEARCH, FORK, an independent audit, or one terminal status:
SOLVED, PARTIAL, CONDITIONAL, INCONCLUSIVE, REFUTED, INFEASIBLE, UNIDENTIFIABLE, BLOCKED, CANCELLED.

## Three-layer flow (v0.3)

- **全景层**（一次建立，贯穿全题）：TRIAGE(读题+D1) → RESEARCH(文献+D-R，前置) → SCOPE_FROZEN(D0 七段重述，含问间依赖) → INPUT_PROFILED(全景分析+数据画像) → CLAIMS_REGISTERED(全局假设 G，D2-G) → CANDIDATES_READY(方法矩阵+D3)。
- **逐问层**（SPi 循环）：子问题分析 → 子问题假设 Si（D2-SPi）→ ATTEMPT 建模求解 → VERIFY 该问验证 → 该问鲁棒性（扰动计划→交互→执行）→ D4 裁决 → REVISE（本问修订）或进入 SPi+1（reason: "SPi 完成，进入 SPi+1"）。
- **收束层**：跨问联动检查（终态 gate 校验全部子问题 DONE + 依赖满足）→ 全题鲁棒性汇总 → 终态硬门 → SOLVED + final-report（整体叙事，非拼凑）。

## Pre-modeling literature research (mandatory)

TRIAGE → RESEARCH → D-R → SCOPE_FROZEN. After the initial task triage and
before D0 restatement is frozen, run the D-R exchange
(interaction-protocol.md): search principles, engineering background, and
methods by direction; write research/sources.jsonl; attach a literature
column to the candidate matrix. Every direction must be traceable to at least
one source. A literature-free direction must be explicitly marked
"原创方向" with its derivation basis. Never search for solutions to the
specific contest problem. Mid-solve evidence gaps use a recorded
RESEARCH backtrack, not an implicit bypass of the initial research phase.

## Interaction gates (v2)

Before EVERY transition run `run-state.mjs gate <dir> --to <status> --reason "..."`
and report one status line in the chat: `[状态] FROM → TO：一句话原因`.
The gate enforces the L1 interaction records (interaction-protocol.md) and the
robustness gate: terminal states require a PASSED robustness-kind obligation
(parameter perturbation × magnitude × conclusion-flip judgment) unless
scope.robustnessExempt is set with a reason.

## Backtracking

- REVISE/RESEARCH reasons MUST reference a decisionStack entry id; the round
  returns to that decision point and tries the next option.
- Backtracking depth is chosen by the failure root cause (recorded in
  failed/issues.md):

| Root cause | Depth | Action |
|---|---|---|
| IMPLEMENTATION / TOOL | attempt | fix and rerun, no backtrack |
| VALIDATION | verify | add obligations, re-verify |
| MODEL (wrong direction) | direction | switch candidate (wall memo) |
| assumption falsified | assumption | revise assumption (revisionHistory) → dependent claims stale → re-verify |
| analysis gap | analysis | update analysisLog → re-derive downstream |
| restatement misunderstanding | restatement | revise problem-brief (re-freeze) |
| RESEARCH_GAP | research | add sources, switch method |

  Backtracking to assumption/analysis/restatement depth is a CONTENT revision
  plus downstream re-verification — the state machine does not rewind; the
  loop is expressed as REVISE cycles and event records.
- FORK records its fork point; each failed branch writes a wall memo
  (run-directory.md) before the next branch starts. A wrong direction always
  returns to the fork point, never mid-branch.
- Every stage problem (DATA/TOOL/IMPLEMENTATION/MODEL/VALIDATION/EVIDENCE/
  RESEARCH_GAP) is recorded in failed/issues.md.

## Dispatch (see subagent-dispatch.md)

- >= 2 independent directions → explorer subagents in parallel, coordinator adjudicates.
- Before terminal: blind verifier subagent for key claims (Standard: 1 per task).
- High-Assurance: auditor subagent (math-modeling-audit) before SOLVED.

## Cleanup gate

Before ANY terminal transition, run the cleanup checklist in run-directory.md
(clean code/, _drafts/, failed/ classification, reproducibility.json,
validate). Note the cleanup in the transition reason.

## Round contract

Each round has one objective and records:

- candidate and assumption delta;
- actual command or derivation artifact;
- new evidence IDs;
- obligations closed;
- issues opened and closed;
- whether auditable progress occurred;
- budget used;
- one next action.

## Progress test

Count progress only when a round closes an obligation, adds reproducible evidence, refutes a candidate, tightens a bound or uncertainty interval, removes a blocker, or weakens an unsupported claim correctly.

Do not count rewording, same-parameter reruns, training-only gains, longer prose, tool exit success, or unverified search titles.

After two no-progress rounds, run a stagnation review. A third no-progress round requires a material fork, user decision, or resumable non-SOLVED status.

## SOLVED gate

SOLVED requires frozen scope, all required obligations passed, critical adversarial checks passed, reproducibility material present, limitations stated, and—under High-Assurance—an independent artifact-only audit.
