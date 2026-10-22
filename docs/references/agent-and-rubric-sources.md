# Agent 与评分框架参考资料

## 已检索资料

| 资料 | 用途 | 采用内容 |
|---|---|---|
| [LLM-MM-Agent](https://github.com/YiFraternity/LLM-MM-Agent) | 数学建模阶段化评价 | 问题识别、问题表述、假设、建模、求解、代码、结果分析七阶段 |
| [MM-Agent / MM-Bench](https://arxiv.org/abs/2505.14148) | 数学建模智能体流程 | 问题分析、模型构造、计算求解、报告生成；分析评价、建模严谨性、实用性与科学性、结果与偏差分析 |
| [OpenAI Agents SDK](https://openai.github.io/openai-agents-js/guides/agents/) | Agent 工具与结构化输出 | Agent、工具调用、`outputType`、上下文和 guardrails |
| [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | 输出可靠性 | 用 JSON Schema 约束评审对象和工具结果 |

## 本轮联网核对的候选项目

| 资料 | 核对结果 | 项目内落点 |
|---|---|---|
| [MathModelingAgent](https://github.com/yohanchen1/MathModelingAgent) | 明确使用 Claim → Obligation → Evidence；把 PASS/FAIL/INCONCLUSIVE 与 SOLVED/CONDITIONAL/INCONCLUSIVE/REFUTED 分开，并强调结论强度必须匹配证据强度。 | `references/upstream/yohanchen1--MathModelingAgent`；`skills/upstream-audit/MathModelingAgent/math-modeling-audit` |
| [MathModeling-skills](https://github.com/zhnnky329/MathModeling-skills) | 提供 consistency、completeness、quality-assurance 三层独立审计，以及 robustness、代码审查、人工决策日志等门禁。 | `references/upstream/zhnnky329--MathModeling-skills`；`skills/upstream-audit/MathModeling-skills` |
| [Agentic Paper Review](https://github.com/ngstcf/agentic-paper-review) | 适合借鉴抽取、专家评审、事实核查、文献检索、批评和综合等角色分工，以及自定义标准和人工监督流程。 | `references/upstream/ngstcf--agentic-paper-review` |
| [arxiv-research-agent](https://github.com/pavelgolikov/arxiv-research-agent) | 引用验证需要检查 source chunk、论文归属和原文 quote；支持度不足的引用不能保留为强结论。 | `references/upstream/pavelgolikov--arxiv-research-agent` |
| [OpenPaper](https://github.com/khoj-ai/openpaper) | 可借鉴确定性引用匹配、反事实问题、多跳证据和锚定式评测。 | `references/upstream/khoj-ai--openpaper` |
| [verify-claims](https://github.com/ShaishavMaisuria/research-paper-lifecycle-skills/tree/main/skills/verify-claims) | 通过主张矩阵和正文/表格数字核对发现过度主张；缺证据时只能补证、缩小或删除。 | `skills/upstream-audit/research-paper-lifecycle-skills/verify-claims` |
| [eval-layer](https://github.com/erezweinstein5/eval-layer) | 适合系统自身评测：rubric、测试样例、judge prompt、harness、校准和 HTML 报告。 | `references/upstream/erezweinstein5--eval-layer` |
| [math-model-agent](https://github.com/chengziyue1222/math-model-agent) | 提供七维论文审查、deep-audit、verify-claims 和 judge_engine 的流程参考。 | `references/upstream/chengziyue1222--math-model-agent`；`skills/upstream-audit/math-model-agent` |
| [math-modeling-skill](https://github.com/Y-love-han/math-modeling-skill) | 适合作为完整竞赛工作流、审计、复现和恢复机制的编排参考，不直接作为运行时依赖。 | `references/upstream/Y-love-han--math-modeling-skill` |

上述快照都带有提交号、抓取时间和文件哈希；状态、完整性及稀疏抓取说明见 [`references/SOURCES.json`](../../references/SOURCES.json) 和各项目的 `SOURCE_MANIFEST.json`。

## 设计取舍

本项目采用问题导向和阶段化评价，但把“官方评分”与“通用诊断”分开保存，避免把不同评分体系静默混合。联网资料只作为可追溯证据来源，不能替代论文内部证据。
