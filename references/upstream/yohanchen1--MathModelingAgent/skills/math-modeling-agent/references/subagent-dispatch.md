# Subagent Dispatch Protocol

The coordinator (main agent) owns the ledger and the decision stack; subagents
produce reports and evidence. Never let a subagent mutate run-state directly.

## Three dispatch classes

| Class | Role (lineage) | When | Count |
|---|---|---|---|
| explorer | parallel candidate exploration (original Modeler lineage) | CANDIDATES_READY, >= 2 independent directions | 1 per direction |
| verifier | blind re-verification (original Analyzer lineage) | before terminal: key numeric/feasibility claims | Standard: 1 per task; High-Assurance: 1 per claim |
| corrector | apply accepted critique and produce the next attempt (original Correction lineage) | after a failed/conditional verdict | 1 per selected direction |
| auditor | artifact-only audit (math-modeling-audit skill) | before SOLVED | High-Assurance: mandatory; else optional |

## Brief template (self-contained; subagents see no parent context)

```text
任务目标：<one claim or one direction, exactly>
输入：<file paths + hashes, run dir is read-only>
已知事实：<data profile / geometry facts / problem restatement excerpt>
允许工具：<explicit list; private raw data never leaves the workspace>
验证要求：<which obligations this subagent must produce evidence for>
输出格式：
  结论（一句话，可证伪）
  方法
  执行记录（命令 + 关键输出 + 退出码）
  证据（证据 ID、等级、局限）
  失败点与反例（若有）
  建议（下一步或放弃理由）
边界：<不准做什么，例如"不得修改 run 文件、不得检索题解">
```

## Adjudication rules

- The coordinator reads every report against its brief; a report without
  reproducible commands or evidence IDs is not accepted.
- Two conflicting reports → a second blind round with both reports as input.
- Blind verification means: the verifier receives the claim, the data, and the
  problem text — never the solver's private reasoning. Its agreement upgrades
  the claim to INDEPENDENTLY_VERIFIED; its disagreement opens a critical issue.
- Every dispatch is recorded in the ledger (candidates / issues) with the
  subagent label, brief hash, and verdict.

## Failure bookkeeping

- A failed or abandoned direction writes a wall memo first
  (`failed/directions/<id>/wall.md` per run-directory.md), then the branch is
  closed. Nothing is deleted; every wrong path stays inspectable.
