# Math-Grill Protocol

Ask one question at a time. Read the problem and attachments first. Ask only questions whose answer can change the model, evidence obligation, or deliverable.

## Minimum routing questions

1. What output is required: number, proof, model, prediction, optimum, or decision?
2. Does data exist, and what is its source?
3. Is the requested claim proof, global optimality, causality, safety, or a useful approximation?
4. What error, confidence, or decision risk is acceptable?
5. Is the result for practice, competition, publication, production, or high-stakes use?

## Problem Brief fields (16, collect all applicable)

1. 问题背景与实际问题；2. 目标；3. 子问题（显式+隐含）；4. 输入数据（来源/质量/单位/时间/分组）；5. 数据质量问题；
6. 决策/状态变量；7. 参数；8. 目标函数/评价指标；9. 约束（等式/不等式/整数/非负/逻辑/初始/边界）；
10. 假设及依据；11. 任务类型（预测/优化/解释/证明/机制/决策）；12. 误差/精度要求；
13. 验证标准；14. 最终交付物；15. 风险与失败模式；16. 不适用字段（标注原因）。

## Layered questioning (v0.3)

- **全景层**：global assumptions (G-class) are grilled once — geometry, data
  quality, physical mechanism, numerical basis; recorded via D2-G before
  CLAIMS_REGISTERED.
- **逐问层**：per-subproblem assumptions (S-class) are grilled when the
  subproblem starts (D2-SPi) — only what is specific to this sub-question.

## Per-subproblem grilling (v2)

- Grill **one subproblem at a time**. Never demand assumptions for Q2 while Q1 is unsolved.
- For each subproblem: ask one question at a time, highest-impact first;
  every answer is recorded as the D2 interaction for that subproblem
  (see interaction-protocol.md).
- Mid-subproblem discoveries that change model structure trigger D2':
  register the new assumption, show it in the chat, ask only if it is model-shaping.
- The 16 Problem Brief fields are filled once at intake for the whole problem;
  subproblem-level analysis and assumptions roll forward per attempt.

## Exchange depth per field

- **用户必须输入**：目标（1,2）、误差/精度要求（12）、验证标准（13）、最终交付物（14）——这些只能来自用户，LLM 不得替用户定。
- **LLM 可推断但必须展示依据**：子问题（3）、决策变量（6）、参数（7）、目标函数（8）、约束（9）、假设（10）、任务类型（11）——每条附依据链（题面原句/数据证据/文献/显式 LLM 判断标记）。
- **LLM 可纯推断但必须展示证据**：数据质量（5）——附画像统计；背景（1）、风险（15）、不适用字段（16）——附理由。

## Deep-interaction rules

- Every answer the LLM infers is PRESENTED with its basis before freezing; the user may challenge any item.
- Open questions, not yes/no gates: after the LLM's analysis, ask "你有哪些补充、纠正或自己的资料？" — not merely "确认吗？".
- High-impact exchanges loop until the user says "可以了".
- Infer before asking.
- Ask the highest-impact unknown first.
- Mark irrelevant fields “not applicable” with a reason.
- Turn “自行判断” into an explicit modeling assumption with risk and sensitivity plan, listed in D2 for later challenge.
- Assumptions are revisable: record revisionHistory and mark dependent claims stale.
- Do not freeze scope while a missing answer can change the problem type or claim strength.
- Do not force a proof problem to invent data or an exploratory analysis to invent an objective function.
