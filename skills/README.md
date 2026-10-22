# 项目内置 Skill 包

本目录保存本项目评审流水线和系统开发会实际使用的 skill 副本。运行时优先从项目内加载；未复制的外部 skill 只作为后续扩展，不影响首版核心流程。

## 评审流水线

- `assets-inventory`：论文、题目、代码、数据和结果资产清点
- `comp-prob-analysis`：赛题拆解、目标/约束/能力清单
- `comp-modeling`：模型、假设、公式、算法和检验方案审查
- `comp-code`：代码实现、结果收集和可复现性检查
- `comp-review`：方向反、重复计量、外推、漏变量和跨问矛盾复核
- `paper-analysis`：数据分析与建模结果检查
- `quality-check`：论文结构、引用、格式和质量审查
- `comp-compile-zh`：中文竞赛论文编译与合规检查
- `comp-compile-en`：英文竞赛论文编译与合规检查
- `research-lit`：研究文献检索和分析
- `arxiv`：arXiv 文献检索、下载和摘要
- `literature-review`：文献综述检索与真实性检查
- `analyze-results`：结果统计、比较和解释
- `result-to-claim`：判断结果能够支持哪些论文结论
- `auto-review-loop`：多轮自动复审
- `auto-review-loop-llm`：OpenAI-compatible LLM 多轮复审
- `auto-review-loop-minimax`：MiniMax 多轮复审变体
- `editor-agent`：论文文件编辑和工作流适配
- `paper-plan`：论文结构规划
- `paper-write-zh`：中文论文写作
- `paper-write`：英文 LaTeX 论文写作

## 系统开发

- `dev-requirement`：需求拆解
- `dev-design`：系统、数据库和 API 设计
- `dev-code-backend`：后端编码
- `dev-code-frontend`：前端编码
- `dev-selfcheck`：依赖、构建、探活和核心功能自测

## 上游审计候选（暂不启用）

从 MathModelingAgent、MathModeling-skills、research-paper-lifecycle-skills 和 math-model-agent 复制的候选审计 skill 位于 `skills/upstream-audit/`。它们只读参考，尚未进入运行时 registry；准入条件和来源映射见 `docs/references/skill-audit-matrix.md`。

## 共享依赖

- `shared-references`
- `shared-scripts`

skill 文件保留原始目录结构，后续更新时应在 `HANDOFF_LOG.md` 记录来源版本、修改内容和验证结果。禁止在 skill 中写入 API 密钥、用户论文或机器专属绝对路径。
