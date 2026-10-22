# 评审协议 v0.1

## 目的

本协议定义数学建模竞赛论文的单篇深度评审契约。它约束证据、结论、评分、状态迁移和人工确认；模型只能提出结构化结果，不能替代确定性协调器推进任务状态。

协议依据：

- [MathModelingAgent](https://github.com/yohanchen1/MathModelingAgent)：Claim → Obligation → Evidence、证据等级和独立核验；
- [LLM-MM-Agent](https://github.com/YiFraternity/LLM-MM-Agent)：问题识别、问题表述、假设、模型构造、求解、代码、结果分析七阶段；
- [MathModeling-skills](https://github.com/zhnnky329/MathModeling-skills)：一致性、完整性、质量保证和稳健性审计；
- [arxiv-research-agent](https://github.com/pavelgolikov/arxiv-research-agent)：来源片段、原文摘录和定位核验。

## 结论与证据

结论状态只有：`SUPPORTED`、`CONDITIONAL`、`INCONCLUSIVE`、`REFUTED`。

证据等级从弱到强为：

```text
NOT_CHECKED < DERIVED < EXECUTED < VERIFIED
             < INDEPENDENTLY_VERIFIED < EXTERNALLY_VALIDATED
```

`SUPPORTED` 要求必要义务全部满足、存在稳定定位、证据等级足够且没有未解决冲突。`CONDITIONAL` 必须列出适用假设或范围。缺证据、无法定位、未运行验证或冲突未解时使用 `INCONCLUSIVE`。`REFUTED` 必须有可定位的反例、重算失败或直接冲突证据；没有定位的“反驳”自动降级为 `INCONCLUSIVE`。

`Claim`、`Obligation`、`Evidence` 和 `Verification` 的 Pydantic 实现位于 `backend/app/domain/review_protocol.py`。当需要根据真实义务和证据对象裁决主张时，调用 `resolve_claim_verdict`，不能只凭证据 ID 数量判断。该函数会检查主张引用的义务是否全部存在、必要义务是否完成、义务证据是否链接到真实 Evidence、证据等级是否至少为 `VERIFIED`，以及反驳是否来自 `countercheck_ids`。

模型直接提交的 `SUPPORTED`/`REFUTED` Claim 或 Finding 会先降级为 `INCONCLUSIVE`；`requested_verdict` 只保存模型请求，最终强结论必须由确定性的证据解析器产生。这样，伪造证据 ID、定位或布尔确认不能直接变成正式结论。

## 评审生命周期

```text
CREATED → INGESTING → ASSETS_FROZEN → RUBRIC_CONFIRMATION
        → EVALUATING → EVIDENCE_AUDIT → ARBITRATING
        → REPORT_READY → FROZEN
```

可见异常/结果状态包括 `DEGRADED`、`FAILED`、`BLOCKED`、`NEEDS_MAJOR_FIXES` 和 `REVIEWABLE`。状态机位于 `backend/app/services/state_machine.py`，事件账本只读返回为 tuple。

硬门禁：

- `ASSETS_FROZEN` 必须带资产冻结确认；
- 进入 `EVALUATING` 必须有已发布量表和人工确认；
- `FROZEN` 必须有最终人工确认；
- `BLOCKED` 只能在新证据具备 `INDEPENDENTLY_VERIFIED` 或 `EXTERNALLY_VALIDATED` 且指纹改变后回到 `EVIDENCE_AUDIT`；
- `BLOCKED` 解锁必须提供带 ID、定位和高等级证据的证据包，不能用布尔值或伪造指纹解锁；
- `REPORT_READY`、`REVIEWABLE` 和 `FROZEN` 都会再次检查累计的 `fatal`/`major` Finding，不能通过省略 Finding 参数绕过结果门禁；
- 模型角色不能以自身名称推进状态；
- 重跑必须使用显式幂等键，输入哈希变化会记录 `STALE_MARKED`，存在未清理的 stale 依赖时不能继续推进。

## 七阶段通用诊断

阶段 ID 和权重固定为：

```text
problem_identification  0.15
problem_formulation     0.15
assumptions             0.15
model_construction      0.20
solving                 0.10
code_implementation     0.15
results_analysis        0.10
```

上游常用 0–10 分。本项目保留 `raw_score_0_10`，并将其归一化为 `normalized_score_0_4 = raw / 10 × 4`。七阶段加权总分为 0–100。论文结构、格式和竞赛合规性作为独立横向 Finding，不偷偷并入七阶段总分。

七阶段必须恰好出现一次，且每项 `CriterionScore.weight` 必须等于协议权重；重复阶段或权重漂移直接拒绝聚合。

## 官方评分

官方评分使用 `ReviewTrack.OFFICIAL`，必须同时提供：

- `rubric_profile_id`；
- `rubric_source_hash`；
- `rubric_decision_id`；
- `rubric_published=true`；
- `human_confirmed=true`。

否则 `CriterionScore` 拒绝创建。正式聚合还必须传入已发布的 `RubricProfile` 与对应的人工 `DecisionLedger`，并校验来源哈希、决策 ID、全部 criterion 和权重逐项一致。官方分数与通用诊断分数分别聚合、分别展示，任何一条评分都不能改变 Claim verdict。

## 研发协作边界

6-luna 和 6.1-sol 只用于本项目研发阶段的分析、编码和审查，不构成产品运行时的强制多智能体架构。默认用 6-luna 并行处理 Schema、量表、测试和运行设计；6.1-sol 只复核跨模块冲突、状态机、公开 Schema 和高风险门禁。

## 配置与验证

- `config/default_rubric.yaml`：七阶段、权重、归一化和证据规则；
- `config/state_machine.yaml`：生命周期、结果状态和门禁声明；
- `config/agent_roles.yaml`：研发协作角色；
- `tests/test_review_protocol.py`：对象、评分和四态；
- `tests/test_evidence_policy.py`：证据定位和降级；
- `tests/test_state_machine.py`：转移、幂等、STALE、BLOCKED 和冻结门禁。

运行协议测试：

```powershell
python -m pytest tests -q
python -m compileall -q backend
```
