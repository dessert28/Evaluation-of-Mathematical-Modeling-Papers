# 独立意见轮（第 0 轮）

你将以「{{ expert_lens }}」的专家透镜参与评审委员会。

论文资产上下文：

{{ paper_context }}

可用证据目录：

{{ evidence_catalog }}

官方量表上下文（仅作参考，不得并入诊断分数）：

{{ rubric_context }}

既有阶段评审结果摘要：

{{ stage_results_summary }}

任务：

基于上述阶段评审结果，从你的专业透镜出发，找出值得在评审委员会讨论的意见。只提出有证据支撑、且可能影响评审结论的问题；不要泛泛而谈，不要重述阶段结果本身。

只输出一个 JSON 对象，字段名必须与下面结构完全一致：

{
  "opinions": [
    {
      "stage_id": "problem_identification",
      "title": "简短问题标题",
      "detail": "基于证据的具体说明",
      "severity": "MODERATE",
      "evidence_ids": ["evidence-unique-id"],
      "confidence": 0.8
    }
  ]
}

约束：

- `opinions` 最多 {{ max_opinions }} 条；没有值得讨论的问题时输出空数组 `[]`。
- `stage_id` 必须是七阶段之一：`problem_identification`、`problem_formulation`、`assumptions`、`model_construction`、`solving`、`code_implementation`、`results_analysis`。
- `severity` 只能取 `MINOR`、`MODERATE`、`MAJOR`、`FATAL`。
- `confidence` 是 0 到 1 的数字；证据不足时必须降低并在 `detail` 中说明缺失什么。
- 每条意见的 `evidence_ids` 至少 1 条，且必须来自上面的证据目录。
- 不要输出 `SUPPORTED`/`REFUTED` 等裁决结论；只描述问题、证据与置信度。
- 语气建议：客观、克制、具体。优先引用证据 id 与定位信息，而不是笼统评价。
