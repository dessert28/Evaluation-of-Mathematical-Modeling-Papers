# Interaction Protocol (v2)

Three interaction layers. Execution details stay autonomous; every
model-shaping decision is visible and user-owned.

## Deep-exchange protocol (v2.6)

Every L1 decision point follows a three-beat exchange, never a one-way
"here is my conclusion, confirm it":

1. **LLM presents a complete analysis with its evidence chain.** Every claim
   inside the analysis carries its basis: an exact quote from the problem
   text, a data statistic, a literature source id, or an explicit
   "LLM judgment" marker. A naked conclusion is not a presentation.
2. **The user responds with substance**: confirmation, correction, background
   knowledge, their own references, or their own judgment. A pure "ok" is
   accepted, but the protocol must have OFFERED the space for substance —
   the questions must be open, not yes/no gates.
3. **The LLM updates the artifact and shows the delta.** The restatement,
   analysis log, assumption list, or candidate matrix is edited and the chat
   shows exactly which points changed because of the user's input.

High-impact points (D0, D-R, D2) may loop beats 2-3 as many times as needed
until the user says "可以了". Mathematical modeling is a deep activity;
"skim and start solving" is a protocol violation.

## Chat-first phase presentation (v0.5)

每个重点环节必须先在聊天正文中展示完整、可读、可追问的文本，不能只写入 artifact，也不能只显示工具调用摘要。顺序固定为：

1. LLM 在聊天中给出完整内容、依据链、当前结论和可能被推翻的条件；
2. 给用户留下纠正、补充背景或确认的机会；
3. 用户确认后记录 chat presentation（content hash、呈现时间、用户确认时间和先于 artifact 的顺序）；
4. 再写入 problem-brief、analysis log、assumptions、model、result 或 report artifact；
5. 最后才允许 run-state transition。

重点阶段与最小呈现内容如下：

| 阶段 | 聊天中必须完整展示 |
|---|---|
| D-R | 检索到的方法/背景、来源、适用范围和限制 |
| D0 / SCOPE_FROZEN | 六段式问题重述、依赖关系和待澄清问题 |
| INPUT_PROFILED | 每个附件的字段、单位、坐标系、范围和异常 |
| D2-G / CLAIMS_REGISTERED | 全局假设、依据、风险、Claims 和 Obligations |
| D3 / CANDIDATES_READY | 候选方向矩阵、选择理由、文献列和排除方向 |
| SP1… / ATTEMPT | 当前子问题的问题分析、输入、假设、目标和边界 |
| MODEL / EXECUTE | 完整模型方案、公式、参数、算法和预期输出 |
| VERIFICATION | 验证路径、反例、容差、结果和未覆盖范围 |
| EVALUATION / CORRECTION | 评价 finding、影响的 Claims、修正方案和 lineage |
| D4 / terminal | 本轮完整结果、证据摘要、局限和最终状态建议 |

run-state 只能验证结构化记录，不能直接观察聊天 UI；因此 chat presentation 是显式的 fail-closed 约束，而不是把写文件误认为已展示。缺失 presentation 时，真实 run 不得进入下一阶段。

## L1 decision points (MUST ask via the question tool)

| Point | Trigger | Question | Default |
|---|---|---|---|
| D0 问题重述 | intake complete | the six-section deep restatement below + open clarification questions | accept + no additions |
| D1 路由 | TRIAGE | task type (prediction/optimization/explanation/proof/…) + assurance mode (Fast/Standard/High-Assurance) | auto-routing result |
| D-R 文献研究 | CLAIMS_REGISTERED (before CANDIDATES_READY) | the literature list by direction (AI-found); user endorses / rejects / adds their own | accept list |
| D2-G 全局假设确认 | CLAIMS_REGISTERED (全景层) | the GLOBAL assumptions that hold for the whole problem (geometry, data, physical mechanism, numerical basis) — each with basis chain + risk | accept all |
| D2 子问题假设确认 | **each subproblem starts** | the assumptions for THIS subproblem only (S-class), each with statement + basis chain + risk | accept all |
| D2' 新假设插问 | mid-subproblem discovery that changes model structure | the new assumption + its effect | record-and-continue |
| D3 方向选择 | CANDIDATES_READY | candidate matrix with a literature column per direction; user picks or authorizes auto | baseline |
| D4 结果裁决 | VERIFY done | verdict + evidence digest + key intermediate results (residual/constraint-violation distributions, figure paths) + failure details | verdict-implied |

## D0 deep restatement — six sections (MANDATORY structure)

1. **题目要点摘录**：the problem's own numbers and constraints, quoted.
2. **背景解读**：the engineering/physical mechanism behind the problem.
3. **数据语义**：every attachment, column by column — meaning, units,
   coordinate system, magnitudes; unreadable artifacts are flagged with the
   minimum representation needed.
4. **隐含信息与歧义清单**：numbered; each entry = the LLM's reading + its
   basis + the risk if the reading is wrong. This is the heart of the
   exchange: the user corrects entries here.
5. **各子问题数学本质判定**：every sub-question of the problem — however
   many there are (one or ten) — is classified (fitting/optimization/
   geometric optics/simulation/…), with why.
5.5 **问间依赖关系**：which sub-questions depend on which (models, data,
   verified claims reused downstream) — the整体感 guarantee: later questions
   REFERENCE earlier verified results instead of re-deriving them.
6. **待澄清问题**：open questions inviting the user to add background,
   correct a reading, or supply their own references — never a yes/no list.

After the user answers, problem-brief.md is updated and the delta is shown.

## D-R literature research (pre-modeling, mandatory)

1. The LLM searches by direction × method for principles and methods only —
   engineering background, methodology papers, textbooks, official docs.
   **Never** search for solutions/answers to the specific contest problem.
2. Findings are written to research/sources.jsonl (author/title/year/venue/
   URL/retrieval date/excerpt with section or theorem/table location/mapped
   direction). Every candidate in the method matrix gets a literature column
   referencing these source ids; a direction with no literature must be
   explicitly marked "原创方向" with its derivation basis.
3. The user is asked: endorse / reject / add their own references. User-added
   references join sources.jsonl with the same fields.
4. The D-R interaction record goes into ledger.scope.interactions; the gate
   refuses CANDIDATES_READY without it.

## Honest boundary of the gate

The gate is a MECHANISM guarantee, not an anti-fraud guarantee: it proves a
record exists, never that the record is true — every interaction record is
written by the agent itself. Falsified records are therefore out of the
gate's reach; the defense against them is the blind verifier subagent
(subagent-dispatch.md), which re-derives key claims from data alone, and the
artifact checks (research/sources.jsonl, attempts/N/report.md) that tie each
record to real files on disk.

## Rules

- D0/D1/D-R: once per task. D2/D3: once per subproblem. D2': only when a
  discovery changes model structure. D4: once per attempt round.
- Every L1 record is appended to `ledger.scope.interactions` as
  `{id, decisionPoint, question, options, userAnswer, timestamp, effectOnModel}`
  or, for explicit auto authorization,
  `{auto: true, decisionPoint, reason}`.
- Run the gate before every transition: `run-state.mjs gate <dir> --to <status> --reason "<...>"`.
  The gate refuses SCOPE_FROZEN without D0+D1, CANDIDATES_READY without D-R,
  ATTEMPT-from-CANDIDATES_READY without D3, terminals-from-VERIFY without D4,
  and REVISE/RESEARCH (from VERIFY) whose reason fails to reference a
  `decisionStack` entry id. The CLI `transition` command enforces the same
  gate and has NO escape hatch. Every D4 record carries the attempt number it
  adjudicates (`attempt: N`); the terminal gate requires the D4 for the
  CURRENT attempt. ATTEMPT from CANDIDATES_READY requires `--subproblem <id>`.
  Terminal gates additionally require `scope.cleanupPassed: true` and the
  current attempt's report.md on disk. Mechanism-level tests and unattended
  batch runs may declare `scope.contractExempt: true` — production modeling
  must never set it.

In v0.5, report/evaluation/terminal transitions also read answer-coverage.json when the v3 ledger has registered requirements. Missing or stale mappings are hard blockers; partial mappings and explicit waivers are conditional-only. EVALUATE and CORRECTION_REQUIRED are non-final lifecycle states. An evaluation finding creates a correction lineage and never rewrites the parent run or silently upgrades a claim.

### Chat-first enforcement

For every major phase, the complete readable content must appear in the chat body before any phase artifact is written or state transition is attempted. The agent must show the evidence chain, current conclusion, limitations and falsification conditions, then invite user correction or confirmation. Only after confirmation may it call recordChatPresentation, write problem-brief/analysis/assumption/model/result/report artifacts, and invoke gate or transition.

A v3 real run has scope.chatFirstRequired=true and stores presentation records in ledger.scope.presentations. Each record must identify its stage, chat channel, content hash, presentedAt, userConfirmedAt, fullTextPresented=true and presentedBeforeArtifact=true. The machine gate cannot observe the UI directly, so it treats a missing or malformed record as a hard blocker and never treats a file-only artifact as proof of chat presentation. Major stages are D-R, D0, INPUT_PROFILED, D2-G, D3, each SPn, MODEL, VERIFICATION, EVALUATION, CORRECTION and D4.

## Phase pace — interactive beats between phases (v2.8)

The exposition is delivered PHASE BY PHASE, never as a firehose. The phase
sequence is: restatement → analysis → assumptions → modeling → solving →
verification → robustness → evaluation. Between every two phases there MUST
be a user interaction point: the completed phase is presented, one line asks
whether to proceed to the next phase, and the user may interrupt, ask for a
deeper explanation of any step of the just-finished phase, or contribute
knowledge. Sensitivity/robustness NEVER follows solving automatically — it
only starts after the verification phase, the user's go-ahead, and its own
D-interaction. Within a phase with ≥3 major steps, offer the user one
interruption opportunity after the first step.

## L2 display points (MUST show, never ask)

- After every attempt round: the 8-section runlog digest (see report-contract.md).
- Before every transition: one status line: `[状态] FROM → TO：一句话原因`.
- When starting any command estimated > 60 s: say what, how long, and what
  continues in parallel (see tool-policy.md).

## L3 interruption

- The user may interrupt at ANY time ("停/换方向/改假设/结束").
- On interrupt: stop the current execution chain immediately, then return to
  the nearest decision point on the stack and ask again.
- An interrupt never leaves the run directory inconsistent: run-state writes
  are atomic and lock-guarded; in-flight background jobs are killed or awaited
  before any transition is recorded.

## Decision stack and backtracking

- Every L1 decision also appends to `ledger.scope.decisionStack`:
  `{id (e.g. D3-SP1), point, choice, at, reason}`.
- REVISE/RESEARCH (from VERIFY) reasons MUST reference the stack entry being
  revisited (e.g. "回退到 D3-SP1：M2-area 违反 0.07% 边长约束，改 M1-cheb").
- A wrong direction returns to its fork point: FORK records the fork entry in
  the stack; each failed branch leaves a wall memo before the next branch runs.
- Assumption revisions keep history: `revisionHistory: [{at, reason, changedTo}]`,
  and every downstream claim/obligation that depended on the old assumption is
  marked `stale: true` with the revising assumption id (see claims-evidence.md).

## Live documents (every phase can be refined later)

Every phase artifact is LIVE: problem-brief.md (restatement), analysisLog,
assumptions, sources.jsonl, methods.md, attempt reports. While solving,
anything discovered that shows an earlier phase was incomplete is patched
INCREMENTALLY — revision record + downstream stale marking — without
re-running completed unaffected work. This is the "解题中不断完善" rule.

## Rolling documents

- Problem restatement: written once at intake (problem-brief.md); only
  referenced afterwards; a restatement edit re-opens scope freeze.
- Problem analysis: written per subproblem and appended on every discovery;
  ledger.subproblems[].analysisLog = `[{at, entry, trigger}]`.
- Assumptions: registered per subproblem, revised incrementally; never assume
  the full problem's assumptions are known up front.
