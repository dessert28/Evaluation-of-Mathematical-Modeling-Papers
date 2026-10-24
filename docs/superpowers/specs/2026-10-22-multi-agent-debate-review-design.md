# 多智能体辩论评审设计规格（v0.1）

> 制定时间：2026-10-22（Asia/Shanghai）
> 状态：已批准并落盘；本次仅要求计划文档，实现（第 13 节迭代 1–5）待后续会话执行，当前未写入实现代码。
> 前置文档：`docs/contracts/review-protocol-v0.1.md`、`docs/contracts/frontend-workbench.md`
> 本文取代计划对话中的草案，作为后续施工的冻结口径。

## 1. 目标

在现有七阶段确定性评审之上增加“评审委员会”辩论层：每轮多位专家先独立给出结构化意见，再阅读彼此意见后结构化辩论，多轮收敛后由确定性聚合产出投票、冲突与收敛结论。全程证据锚定、可审计、可复现，且不破坏现有确定性安全边界。

## 2. 成功标准

1. 一次评审可完成 `七阶段 → 辩论（K 专家 × N 轮）→ EVIDENCE_AUDIT`，辩论快照持久化（轮次、意见、发言、置信度、投票、冲突、收敛指标）。
2. 既有 132 项后端测试与前端 6 项测试保持通过；新增辩论测试通过。
3. `SUPPORTED`/`REFUTED` 仍只能由 `resolve_claim_verdict` 产出；无证据 `REFUTE` 被拒绝；官方/诊断双轨不受影响。
4. 前端可查看专家意见时间线与每轮辩论；辩论数据不进入 3 秒轮询的 job 响应。
5. 每个迭代追加 `HANDOFF_LOG.md` 并通过 `scripts/check_handoff.py`。

## 3. 非目标

- 不引入 LangGraph / CrewAI / AutoGen 等框架，沿用现有 OpenAI-compatible adapter。
- 不新增证据来源、不执行上传代码、不改七阶段 prompt 与权重、不改状态机。
- v0.1 不增加 LLM“主席”改写调用：聚合是确定性纯函数。
- 不把辩论结论自动提升为最终 Finding（后续迭代）。
- 不引入数据库迁移框架，沿用 `_ensure_additive_schema_compatibility` 加列。

## 4. 架构

```
自动运行线程（ReviewRunManager._execute）
  └─ AutomaticReviewRunner.run()            # 七阶段，不变
  └─ 全部阶段 COMPLETED 且 options.debate.enabled（默认 true）
       └─ DebateService.run_sync(review_id, options)
            ├─ round 0：K 专家并行独立出意见（PanelOpinion）
            ├─ round 1..N：匿名交叉辩论（DebateMessage）
            ├─ 每轮落库；收敛判定；预算/轮数上限
            └─ 确定性聚合 → DebateOutcome
  └─ coordinator.transition(EVIDENCE_AUDIT)  # 状态机不变

手动触发：POST /api/v1/reviews/{id}/debate/run → DebateRunManager.submit()（后台线程）
```

`ReviewJob` 状态机与 `state_snapshot` 不变；辩论数据存 `review_jobs.debate_snapshot` 独立 JSON 列，避免轮询膨胀。

## 5. 领域契约（`backend/app/domain/debate.py`）

纯数据 + 纯函数，无 I/O、无模型调用。

- `Stance`：`AGREE / QUALIFY / DISAGREE / REFUTE / WITHDRAW`
- `DebateStatus`：`QUEUED / RUNNING / COMPLETED / DEGRADED / FAILED / INTERRUPTED`
- `OpinionDraft`：模型输出草稿（`stage_id` 必须在七阶段内、`evidence_ids` 至少 1 条、`confidence` 0–1、文本长度上限）。
- `PanelOpinion`：落库契约，`expert_id` 由引擎赋值匿名 id，`id` 由引擎重写为 `op-{round}-{expert}-{n}`。
- `MessageDraft`：模型输出草稿（`target_opinion_id`、`stance`、`evidence_ids`、`confidence`、`rationale`、可选 `revised_*`）。
- `DebateMessage`：落库契约，`id` 由引擎重写为 `msg-{round}-{expert}-{n}`；`REFUTE` 必须带证据（validator 强制）。
- `DebateRound`：`round_number`、`speaker_order`（种子化乱序记录）、`status`、`opinions`（round 0）、`messages`（round ≥ 1）、`rejected`。
- `DebateOutcome`：`rounds_run`、`converged`、`agreement_ratio`、`accept_threshold`、`accepted_opinion_ids`、`conflict_opinion_ids`、`vote_tally`、`stop_reason`（`converged/max_rounds/budget_exhausted/failed`）。
- `DebateSnapshot`：`review_id`、`status`、`panel`（匿名映射）、`config`、`rounds`、`outcome`、`call_budget`、`stale`、`last_error`、时间戳。
- `PanelOpinionBatch` / `DebateMessageBatch`：adapter 结构化输出包装。

确定性聚合（纯函数，单测覆盖）：

```
stance_weight：AGREE=+1, QUALIFY=+0.5, DISAGREE=-1, REFUTE=-2, WITHDRAW=0
score(opinion) = Σ stance_weight(stance) × expert_weight + (fatal ? fatal_bonus : 0)
accepted：score ≥ accept_threshold（默认 0.5）
conflict：同时出现正负立场且 |score| < accept_threshold
agreement_ratio = 末轮无 DISAGREE/REFUTE 的意见数 / 意见总数
converged = agreement_ratio ≥ agreement_threshold（默认 0.8）且 rounds_run ≥ min_rounds
```

公开函数：`aggregate_votes`、`detect_conflicts`、`compute_agreement`、`evaluate_panel`。

## 6. 面板配置（`config/debate.yaml` + `backend/app/services/debate_panel.py`）

默认 5 位专家：`modeling / algorithm / statistics / code / writing`，权重均等 1.0。配置项：`max_rounds(2, 上限 5)`、`min_rounds(1)`、`agreement_threshold(0.8)`、`accept_threshold(0.5)`、`fatal_bonus(3)`、`max_calls(30)`、`reject_retry(1)`、`anonymize(true)`、`max_opinions_per_expert(8)`。文件缺失或非法时回退内置默认（fail-open），不阻塞评审。

## 7. 提示词资产（`config/prompts/v0.1/debate/`）

- `system.md`：辩论系统提示词（只输出 JSON、证据必须定位、无证据降级、不得自判强结论）。
- `panel_opinion.md`：独立意见模板（论文上下文、证据目录、阶段结果摘要、专家透镜）。
- `debate_message.md`：发言模板（匿名意见集、历史发言、轮次、已知证据 id）。

`PromptTemplateStore.debate_prompt(kind, **values)` 读取并渲染；JSON Schema 由 adapter 自动附加。

## 8. 持久化（`backend/app/db.py`）

- `ReviewJobRecord.debate_snapshot`：`JSON NOT NULL DEFAULT '{}'`。
- `_ensure_additive_schema_compatibility` 增加该列声明（旧库自动 ALTER）。
- `SqlAlchemyReviewJobRepository.save_debate_snapshot / get_debate_snapshot`，沿用 `save_result_snapshot` 的原子替换模式。

## 9. 运行器与 API

`ReviewRunManager`：

- 注入 `debate_service`；七阶段全部 COMPLETED 后、`EVIDENCE_AUDIT` 转换前调用 `run_sync`。
- 开关 `job.options["debate"]["enabled"]`，默认 `True`；`max_rounds/expert_ids` 可覆盖。
- 辩论失败不阻塞阶段结果：run 置 `DEGRADED` + `last_error.code=debate_failed`，仍转 `EVIDENCE_AUDIT`，可手动重跑。
- 启动恢复时把进行中的辩论置 `INTERRUPTED`。
- 阶段重跑后把 `debate_snapshot.stale` 置 `true`。

API（`backend/app/api/reviews.py`）：

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/reviews/{id}/debate` | 辩论快照；无则 404 `debate_not_found` |
| POST | `/api/v1/reviews/{id}/debate/run` | `{idempotency_key, max_rounds?, expert_ids?}` → 202；409 `debate_already_active` / `debate_not_ready` / `review_not_ready` / `idempotency_conflict` |
| GET | `/api/v1/reviews/{id}/debate/rounds/{round}` | 单轮明细；越界 404 |

`ReviewRunRequest` 增加可选 `debate` 对象（向后兼容）。

## 10. 前端展示

`frontend/src/components/DebateTimeline.jsx`：状态徽章、收敛进度、专家 chips、轮次切换、意见卡片（severity/confidence/证据）、发言列表（stance 配色）、被拒发言折叠、“运行/重跑辩论”按钮。`ReviewDetail.jsx` 在结果区上方挂载；辩论数据不进入 3 秒轮询。

## 11. 失败模式

| 场景 | 行为 |
|---|---|
| 模型未配置 / `llm_not_configured` | 辩论 `FAILED`，阶段保留，run `DEGRADED` |
| 阶段或证据为空 | 409 `debate_not_ready`，不调用模型 |
| 意见证据引用不存在 | 拒绝并记录，重试 `reject_retry` 次 |
| `REFUTE` 无证据 | 模型层拒绝；重试后仍失败则记录拒绝 |
| 某轮全部专家失败 | 有有效轮次 → `DEGRADED`；否则 `FAILED` |
| 轮数/预算耗尽 | `stop_reason=max_rounds/budget_exhausted`，`converged=false` |
| 重复启动 | 409 `debate_already_active` |
| 服务重启 | 恢复为 `INTERRUPTED` |
| 阶段重跑 | 辩论 `stale=true` |
| 专家数 < 2 / 未知专家 | 422 `invalid_panel` |

## 12. 测试计划

新增 `tests/test_debate_models.py`、`test_debate_aggregation.py`、`test_debate_engine.py`、`test_debate_api.py`、`test_review_run_debate_integration.py`；扩展 `frontend/tests/api.test.mjs`。复用 `Store/Adapter` 假对象风格，不新增真实网络依赖。

## 13. 迭代计划

| 迭代 | 内容 | 门禁 |
|---|---|---|
| 0 | 本规格、`docs/contracts/debate-protocol-v0.1.md`、`config/debate.yaml`、交接更新 | check_handoff |
| 1 | `domain/debate.py` + 模型/聚合单测 | pytest + compileall |
| 2 | `debate_panel.py`、`debate_engine.py`、`db.py`、prompt_templates、提示词、测试 | pytest + compileall |
| 3 | `review_run_manager.py`、`stage_orchestrator.py`、`api/reviews.py`、`main.py`、测试 | pytest + compileall |
| 4 | 前端 `api.js`、`DebateTimeline.jsx`、`ReviewDetail.jsx`、前端测试与构建 | npm test + build |
| 5 | 全量验收、交接收尾（可选：缺陷注入自评测） | 全部命令 |

每轮验证命令：

```powershell
.venv\Scripts\python.exe -m pytest tests -q --basetemp .pytest_tmp
.venv\Scripts\python.exe -m compileall -q backend
python scripts/check_handoff.py
python references/_tools/verify_snapshots.py
npm run test --prefix frontend     # 迭代 4/5
npm run build --prefix frontend    # 迭代 4/5
```

## 14. 风险与假设

- 风险：不同端点 JSON 遵循度不一 → 现有 schema 重试 + 拒绝重试兜底；成本 K×轮数 → `max_calls` 限制。
- 风险：快照体积 → 意见数/文本长度/轮数均设上限。
- 假设：v0.1 专家权重均等；`fatal_bonus=3`；辩论默认自动执行；手动重跑需幂等键。
- 未决（后续迭代）：采纳意见合并进 `ReviewResult.findings`、报告章节、ICC 校准、缺陷注入基准。
