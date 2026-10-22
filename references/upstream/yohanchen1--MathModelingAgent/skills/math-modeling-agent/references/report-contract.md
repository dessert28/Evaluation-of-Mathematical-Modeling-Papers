# Report Contract

## Attempt report

Every attempt report contains exactly:

1. one round objective;
2. candidate/direction;
3. assumption delta;
4. claims changed;
5. actual execution or derivation artifacts;
6. new evidence IDs;
7. obligations closed;
8. issues opened and closed;
9. delta from prior attempt;
10. valid-progress decision;
11. budget usage;
12. current status;
13. one next action.

Do not copy full prior solutions or private reasoning.

## Terminal report

State the frozen question, final scientific status, answer/recommendation, verified claims and evidence links, conditional/unresolved claims, assumptions and sensitivity, candidate comparison, data and parameter sources, validation, failure cases, limitations, reproducibility commands, and resume conditions when non-SOLVED.

整体感 requirement (v0.3): the terminal report is ONE narrative, not a
concatenation of sub-question reports — it must show the question-dependency
chain (which model fed which), the shared global assumptions, and the
cross-sub-question consistency checks. A reader must be able to see the whole
problem as one connected argument.

## Chat display — the runlog digest (MUST output, v2.7)

The following is shown DIRECTLY IN THE CHAT, not only on disk.

### Readability standard — write for a human reader, never a bullet list

Every section is an EXPOSITION, not a summary: state WHY the step is taken,
HOW the reasoning runs (derivation, mechanism, first-principles chain), WHAT
came out (numbers with units), and HOW it is checked. A reader who knows
nothing about the problem must be able to follow each section without
guessing.

Style: step-by-step numbered exposition with plain direct language (this is
a working document, not a final paper — no paper-style formal phrasing
required), but with MORE detail than a paper would carry: every parameter
choice gets its reason, every formula is followed by a plain-language
explanation of each symbol, every step ends with a transition line
("这一步保证了…，为下一步…做好准备"), and every conclusion states what it
would take to be wrong. Minimum expectations per section:

- 问题重述：restate the question in your own words, explaining every
  parameter's meaning and where it comes from in the problem text.
- 问题分析：walk the physical/geometric mechanism step by step (e.g. why the
  nodes move radially, how the focal geometry pins the paraboloid), each
  step justified by problem text, data, or derivation.
- 模型假设：for EVERY assumption give the reason it is justified
  (original wording / data statistic / derivation / literature) and what
  happens if it fails.
- 模型建立与求解：write the derivation in full (equations, variable
  definitions, units, how the equation is solved, numerical method and why
  it was chosen), not just the final formula.
- 验证：explain the verification LOGIC for each obligation (what would
  falsify it, what tolerance is used and why), then the outcome.
- 鲁棒性：for each perturbation say what was varied, why that parameter,
  and what would count as a conclusion flip.
- 评价与改进 / 参考文献：state the comparison criterion and map each
  reference to the exact method it supports.

### Intake digest (once, at intake completion) — the six-section deep restatement

【题目要点摘录】the problem's own numbers and constraints, quoted, each explained
【背景解读】engineering/physical mechanism, walked through
【数据语义】every attachment column by column (meaning/units/coordinate system/magnitudes), with observed statistics
【隐含信息与歧义清单】numbered; each = LLM reading + derivation/basis + risk (the user corrects entries here)
【各子问题数学本质判定】every sub-question (any count) classified + why
【待澄清问题】open questions inviting user background/corrections/references

After the D0 exchange, show the delta applied to problem-brief.md.

### Quality self-check (MUST run before every D4 verdict)

Before presenting a D4 verdict, run the self-check on the current attempt's
report and show the result in the chat: for each of the eight digest sections,
confirm whether it answers all four questions — WHY (why this step), HOW
(how the reasoning runs), WHAT (result with units), CHECK (how it is
verified, or what would falsify it). Any section failing one of the four is
flagged as incomplete and the round is NOT presented for verdict until fixed.
The self-check is a human-facing declaration: the user decides whether the
exposition is actually sufficient. This is the quality gate; the machine
gates above only guarantee existence and structure.

### Per-round digest (after EVERY attempt round)

```text
## Attempt N 摘要
问题重述：<1-2 sentences, current subproblem>
问题分析：<2-4 sentences, this round's inputs/insights/delta vs last round>
模型假设：<沿用 X 条 + 新增 Y 条 + 修订 Z 条；修订注明原因；重中之中，不得省略>
模型建立与求解：<core equations + method + key numbers>
验证：<obligations ✓/✗ + evidence levels + most important failure>
鲁棒性：<this round's sensitivity results, or "未覆盖，计划在 attempt M">
评价与改进：<candidate comparison / limitations / next improvement>
参考文献：<new citations or "无新增">
```

Rules:
- The restatement is frozen after intake; analysis and assumptions ROLL FORWARD
  per subproblem and per round (they change, and the digest shows the delta).
- Private chain-of-thought is never shown; only auditable content.
- The digest is a hard requirement of the round contract: a round whose digest
  is missing does not count as a completed round.

## Cleanup checklist (before ANY terminal transition)

1. attempts/<n>/code holds only final reproducible scripts with header comments.
2. Exploratory/buggy code is moved to _drafts/ or failed/code-drafts/ — never deleted.
3. No debug prints or machine-specific hardcoded paths.
4. figures → plots/, tables → data/, deliverable at run root.
5. reproducibility.json matches the final scripts.
6. run-state validate passes; every obligation has a terminal status.

## v0.5 machine contract

Every attempt report contains the nine scientific sections in this order: 问题重述、问题分析、模型假设、符号说明、模型建立与求解、验证、鲁棒性分析、模型的评价与改进、参考文献. The existing 13 administrative fields remain front matter and are not a substitute for scientific exposition.

The report validator emits section coverage, WHY/HOW/WHAT/CHECK diagnostics, symbol errors, unsupported claim language, evidence references and requirement coverage. Missing or stale requirement coverage blocks report/evaluation/terminal transitions; partial coverage may only produce CONDITIONAL.

The paper-evidence directory is an evidence package, not a silently generated manuscript. Every section cites claim/evidence IDs and preserves limitations, failures and unresolved scope.
