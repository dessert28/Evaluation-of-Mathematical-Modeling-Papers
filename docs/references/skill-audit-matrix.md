# 数学建模论文评价能力核对矩阵

本矩阵把外部项目的能力映射到本系统的证据链、七阶段诊断和产品流程。`参考` 表示只读来源，`候选` 表示已复制到 `skills/upstream-audit/`、待适配和测试，`启用` 才表示进入运行时 registry；当前没有外部快照被标记为启用。

## 结论状态机

MathModelingAgent 的 Claim → Obligation → Evidence 结构适合作为本系统的结论底座。每条结论必须包含主张、所需义务、证据跨度、证据质量、反例/冲突和审计时间，并使用四态：

| 状态 | 含义 | 允许的下一步 |
|---|---|---|
| `SUPPORTED` | 证据直接覆盖主张，且没有未解决冲突 | 可进入评分和建议 |
| `CONDITIONAL` | 仅在明确假设、范围或数据条件下成立 | 缩小表述、补条件或补验证 |
| `INCONCLUSIVE` | 证据不足、定位失败或验证未完成 | 待人工核实，不得写成通过 |
| `REFUTED` | 反例、重算或证据冲突直接否定主张 | 标记严重问题并要求修复 |

`PASS/FAIL` 只作为外部 skill 的兼容输入，进入本系统后必须映射为上述四态；没有证据时默认 `INCONCLUSIVE`，不能自动补证据。

## 候选能力

| 来源 | 项目内位置 | 吸收的能力 | 适用阶段 | 状态 |
|---|---|---|---|---|
| MathModelingAgent | `skills/upstream-audit/MathModelingAgent/math-modeling-audit` | 独立主张审计、证据等级、反例、可复现性、MCM/ICM 终审边界 | 证据绑定、逻辑对抗复核 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/consistency-auditor` | 数字、符号、单位、参数和论文/代码/数据跨媒介一致性 | 证据绑定、终审 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/completeness-auditor` | 完整性、缺失项和提交前门禁 | 资产清点、合规检查 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/quality-assurance-auditor` | 独立 QA 审计和最终质量闸门 | 汇总、报告发布前 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/robustness-checker` | 敏感性、边界、误差和稳健性检查 | 验证与稳健性 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/modeler-decision-logger` | 记录人工选模、假设和冻结决策 | 人工确认、重跑 | 候选 |
| MathModeling-skills | `skills/upstream-audit/MathModeling-skills/code-reviewer` | 代码可读性、运行路径和结果复现审查 | 代码/数据审计 | 候选 |
| research-paper-lifecycle-skills | `skills/upstream-audit/research-paper-lifecycle-skills/verify-claims` | 主张矩阵、正文/表格数字核对、back/scope/cut 处理 | 主张核验、建议生成 | 候选 |
| math-model-agent | `skills/upstream-audit/math-model-agent/review-paper.md` | 七维并行审查和评审汇总思路 | 通用诊断评分 | 候选 |
| math-model-agent | `skills/upstream-audit/math-model-agent/deep-audit.md` | 深度审计、权限边界和多层验证 | 逻辑对抗复核 | 候选 |
| math-model-agent | `skills/upstream-audit/math-model-agent/verify-claims.md` | claim/evidence 核对方向 | 证据绑定 | 候选 |
| math-model-agent | `skills/upstream-audit/math-model-agent/judge_engine.md` | 多模型仲裁、权重和解析约束参考 | 评分汇总 | 候选 |

## 仅作设计参考的项目

- `references/upstream/YiFraternity--LLM-MM-Agent`：保存七阶段评测提示词、结构化输出和 MMBench 量表样例；不直接复制其评分实现。
- `references/upstream/ngstcf--agentic-paper-review`：用于角色分工、可配置官方 rubric、人工监督和多模型 judge 的产品流程设计。
- `references/upstream/pavelgolikov--arxiv-research-agent`：用于来源 chunk、论文归属、原文 quote 和 0/1/2 支持度检查。
- `references/upstream/khoj-ai--openpaper`：用于确定性引用匹配、反事实问题和多跳证据评测。
- `references/upstream/erezweinstein5--eval-layer`：用于 rubric、测试样例、LLM judge prompt、校准和 HTML 评测报告。
- `references/upstream/Y-love-han--math-modeling-skill`：用于全流程编排和恢复边界；其整体流程不会未经拆分直接接管本系统。

## 运行时准入门槛

外部候选 skill 必须同时满足：

1. 输出能转换为 Pydantic/JSON Schema；
2. 每条结论能绑定证据定位；
3. 缺证据时会降级为 `INCONCLUSIVE` 或 `CONDITIONAL`；
4. 不修改被审论文，不执行不受信任代码；
5. 有固定夹具、失败用例和交接日志；
6. 许可证与上游来源可追溯。

