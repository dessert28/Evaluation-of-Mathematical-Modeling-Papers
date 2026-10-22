# 数学建模论文评价与优化建议智能体设计规格

## 目标

构建一个本地优先的 Web + API 系统，接收数学建模竞赛论文及可选题目、代码、数据和官方评分标准，输出两套相互独立的结果：

1. 按用户选定官方评分标准生成的评分结果；
2. 按通用数学建模诊断量表生成的阶段化诊断结果。

系统还要生成有证据定位的优化建议，并保留每次施工的完整交接记录。

## 设计原则

- **证据优先**：结论必须引用文件、页码、段落或代码位置。
- **阶段化**：把评价拆成可独立运行和重跑的阶段。
- **标准可替换**：官方评分标准可导入、预览、修改、发布和版本化。
- **结果不混算**：官方评分与通用诊断并列展示。
- **本地隐私优先**：默认文件和结果留在本机，不上传到第三方存储。
- **模型可替换**：只依赖 OpenAI-compatible API 协议，不锁定单一厂商。
- **失败可见**：解析失败、检索失败、模型输出不合规和证据缺失都必须进入结果状态。

## 处理流程

```text
资产清点
  → 题目/目标解析
  → 官方量表解析与人工确认
  → 阶段化诊断评价
  → 可选代码/数据静态审计
  → 逻辑对抗复核
  → 证据绑定与一致性检查
  → 官方评分与通用诊断并列汇总
  → 优化建议、Markdown/JSON 报告
```

## 评价量表

通用诊断由七个维度组成，评分范围为 0–4 分，换算为 0–100 分：

| 维度 | 权重 | 评价重点 |
|---|---:|---|
| 问题识别与理解 | 15% | 目标、子问题、约束、关键变量是否准确对应题面 |
| 问题表述、变量与假设 | 15% | 变量定义、假设理由、边界和量纲 |
| 模型构造 | 20% | 模型选择、目标函数、约束、推导闭环 |
| 求解方法与正确性 | 15% | 算法适配性、收敛/求解过程、结果合理性 |
| 代码与可复现性 | 15% | 代码、参数、随机种子、运行说明和结果来源 |
| 验证、灵敏度与稳健性 | 10% | 回代、对比、敏感性、误差和局限性 |
| 论文结构与合规性 | 10% | 章节、图表、引用、格式和结论支撑 |

发现按 `fatal`、`major`、`minor` 分级。`fatal` 使任务状态为 `blocked`；无 fatal 但有 major 时为 `needs_major_fixes`；否则为 `reviewable`。严重度不修改原始分数。

## 官方评分标准

支持 PDF、DOCX、Markdown、JSON 四类输入。导入后转换为：

```json
{
  "name": "官方评分标准名称",
  "version": "版本号",
  "source_asset_id": "资产 ID",
  "criteria": [
    {
      "id": "criterion-1",
      "label": "标准项名称",
      "description": "评分要求",
      "weight": 20,
      "scale_min": 0,
      "scale_max": 100,
      "evidence_required": true
    }
  ]
}
```

发布前必须显示可编辑预览。每个评审任务绑定一个已发布版本，并保存源文件哈希、解析警告和发布时间。

## 公共 API

| 方法 | 路径 | 行为 |
|---|---|---|
| POST | `/api/v1/rubrics/import` | 上传评分标准并生成草稿 |
| POST | `/api/v1/rubrics/{id}/publish` | 发布量表版本 |
| GET | `/api/v1/rubrics` | 列出量表 |
| POST | `/api/v1/reviews` | 创建评审任务 |
| GET | `/api/v1/reviews/{id}` | 查询进度和结果 |
| POST | `/api/v1/reviews/{id}/rerun` | 重跑指定阶段 |
| GET | `/api/v1/reviews/{id}/report?format=md\|json` | 导出报告 |
| GET | `/health` | 服务探活 |

## 核心对象

- `Asset`：文件名、类型、大小、SHA-256、解析状态、文本块。
- `RubricProfile`：来源、版本、标准项、权重、解析警告、发布状态。
- `ReviewJob`：资产、量表、阶段状态、诊断分、官方评分、任务状态。
- `EvidenceSpan`：资产 ID、页码/段落/行号、原文摘录、定位置信度。
- `CriterionScore`：标准项、分数、证据、理由、置信度。
- `Finding`：类别、严重度、位置、证据、影响、规则来源。
- `Recommendation`：关联问题、优先级、修改动作、验收条件、工作量。
- `HandoffEntry`：时间、操作者、目标、修改、验证、风险和下一步。

## 安全与失败行为

- API 密钥只从环境变量读取，禁止写入仓库和报告。
- 上传文件写入配置目录，限制文件大小并记录 MIME 类型。
- 默认不执行上传代码，只做静态资产清点和文本审计。
- OpenAI-compatible 返回无法通过 schema 校验时，有限次数重试；仍失败则任务进入 `failed` 并保留原始错误摘要。
- 搜索失败不阻塞本地论文评价，报告标记检索不可用。
- 无法定位证据的模型结论必须降级为“待人工核实”。

## 外部参考

- [LLM-MM-Agent](https://github.com/YiFraternity/LLM-MM-Agent)
- [MM-Agent 与 MM-Bench](https://arxiv.org/abs/2505.14148)
- [OpenAI Agents SDK](https://openai.github.io/openai-agents-js/guides/agents/)
- [Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
