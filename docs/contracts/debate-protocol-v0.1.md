# 辩论评审协议 v0.1

## 目的

本协议定义多专家辩论评审的可执行契约：轮次结构、发言立场、证据规则、收敛判定、确定性投票与失败状态。它约束模型只能提出结构化意见与发言，不能替代确定性聚合推进结论；强结论仍由 `review-protocol-v0.1.md` 中的证据解析器产出。

## 角色

| 角色 | 产生方式 | 职责 |
|---|---|---|
| 专家（Expert） | `config/debate.yaml` 中的面板配置，匿名化为 `expert-1..K` | 独立出意见；阅读他人意见后结构化发言 |
| 引擎（Engine） | 确定性代码 | 调度轮次、重写 id、校验证据、落库、计算收敛与投票 |
| 主席（Chair） | 确定性聚合函数（v0.1 无 LLM） | 加权投票、冲突识别、产出 `DebateOutcome` |

## 轮次结构

```text
Round 0（独立意见）  每位专家看不到他人输出，产出 0..N 条 PanelOpinion
Round 1..N（辩论）  专家按种子化随机顺序发言，针对已有意见产出 DebateMessage
逐轮落库            每轮结束后计算 agreement_ratio，达到阈值或达到 max_rounds 即停
终局                 evaluate_panel 产出投票、冲突、收敛结论
```

- 发言顺序由 `random.Random(f"{review_id}:{round}")` 生成并记录在 `speaker_order`，保证可复现。
- 匿名化：模型只看到 `expert-1..K` 编号与透镜描述，看不到具体模型或专家配置 id。
- 轮数上限默认 2（配置上限 5）；`min_rounds` 默认 1。

## 发言立场

| 立场 | 含义 | 证据要求 |
|---|---|---|
| `AGREE` | 同意该意见 | 可选；有则更优 |
| `QUALIFY` | 部分同意，补充适用条件 | 可选 |
| `DISAGREE` | 不同意，但未构成反驳 | 建议提供 |
| `REFUTE` | 有可定位证据的反驳 | **必须至少一条证据**，否则协议拒绝 |
| `WITHDRAW` | 作者撤回自己的意见 | 不需要 |

- 每条发言必须给出 `target_opinion_id`、`confidence`（0–1）与 `rationale`。
- `revised_title / revised_detail / revised_severity` 为可选的修订建议；v0.1 只记录修订，不原地改写意见。
- 证据引用只能使用冻结论文中已存在的 `evidence_id`（来自七阶段结果）；引用不存在即拒绝。

## 收敛与投票

```text
stance_weight：AGREE=+1, QUALIFY=+0.5, DISAGREE=-1, REFUTE=-2, WITHDRAW=0
score(opinion) = Σ stance_weight(stance) × expert_weight + (fatal ? fatal_bonus : 0)
accepted       = score ≥ accept_threshold（默认 0.5）
conflict       = 同时出现正负立场且 |score| < accept_threshold
agreement_ratio = 末轮无 DISAGREE/REFUTE 的意见数 / 意见总数
converged      = agreement_ratio ≥ agreement_threshold（默认 0.8）且 rounds_run ≥ min_rounds
```

`stop_reason` 仅四种：`converged`、`max_rounds`、`budget_exhausted`、`failed`。

## 状态

`QUEUED → RUNNING → COMPLETED | DEGRADED | FAILED`；服务重启时进行中的状态恢复为 `INTERRUPTED`。`DEGRADED` 表示部分轮次或部分专家失败但仍有有效轮次；`FAILED` 表示没有可用的意见产出。阶段重跑后快照标记 `stale=true`。

## 错误码

`debate_not_found`、`debate_not_ready`、`review_not_ready`、`debate_already_active`、`idempotency_conflict`、`invalid_panel`、`invalid_round`、`llm_not_configured`、`debate_budget_exhausted`、`debate_message_rejected`、`debate_failed`、`debate_unavailable`。错误消息不得包含模型端点、密钥或论文正文。

## 与既有协议的关系

- 辩论只处理 `Finding/Claim` 级别的意见，不新增证据、不修改七阶段分数、不影响官方/诊断双轨。
- 辩论的“接受意见”是建议集合；最终报告与结论仍以 `ReviewResult` 与 `resolve_claim_verdict` 为准。
- 人工确认门禁不变：辩论快照只读展示，人工可在后续迭代中确认采纳。
