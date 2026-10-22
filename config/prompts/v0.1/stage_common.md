# 七阶段评审公共指令

评审阶段：{{ stage_id }}（{{ stage_name }}）

论文资产上下文：
{{ paper_context }}

可用证据目录：
{{ evidence_catalog }}

官方量表上下文（只作参考，不得并入通用诊断分数）：
{{ rubric_context }}

已有阶段结果：
{{ prior_results }}

请完成本阶段检查：{{ checks }}

只输出一个 JSON 对象。字段名必须与下面结构完全一致，不得使用 description、statement、evidence_refs、conclusion 等同义字段。

{
  "stage_id": "{{ stage_id }}",
  "raw_score_0_10": 0,
  "rationale": "基于证据的简洁理由",
  "evidence": [
    {
      "id": "evidence-unique-id",
      "kind": "document",
      "asset_id": "asset-id",
      "block_id": "block-id",
      "page": 1,
      "paragraph": null,
      "line_start": null,
      "line_end": null,
      "quote_hash": null,
      "evidence_level": "NOT_CHECKED",
      "limitations": []
    }
  ],
  "obligations": [
    {
      "id": "obligation-unique-id",
      "text": "本阶段必须满足的具体要求",
      "required": true,
      "fulfilled": true,
      "evidence_ids": ["evidence-unique-id"],
      "limitations": []
    }
  ],
  "claims": [
    {
      "id": "claim-unique-id",
      "exact_text": "论文中的主张或可复核的判断",
      "type": "problem_understanding",
      "scope": null,
      "assumptions": [],
      "obligation_ids": ["obligation-unique-id"],
      "evidence_ids": ["evidence-unique-id"],
      "countercheck_ids": [],
      "verdict": "INCONCLUSIVE",
      "limitations": [],
      "locations": []
    }
  ],
  "findings": [
    {
      "id": "finding-unique-id",
      "title": "问题标题",
      "detail": "问题说明",
      "severity": "minor",
      "verdict": "INCONCLUSIVE",
      "evidence_ids": ["evidence-unique-id"],
      "claim_ids": ["claim-unique-id"],
      "locations": []
    }
  ]
}

约束：

- raw_score_0_10 必须是 0 到 10 的数字。
- evidence 至少包含一条真实、可定位的证据；优先使用证据目录中存在的 block_id，并保持 page、paragraph、line_start、line_end 与目录一致。
- evidence_level 只能使用 NOT_CHECKED、DERIVED、EXECUTED、VERIFIED、INDEPENDENTLY_VERIFIED、EXTERNALLY_VALIDATED。
- verdict 只能使用 SUPPORTED、CONDITIONAL、INCONCLUSIVE、REFUTED。
- severity 只能使用 fatal、major、minor。
- obligations[].evidence_ids、claims[].evidence_ids、findings[].evidence_ids 必须引用本对象 evidence 数组中已有的 id。
- claims[].obligation_ids 必须引用本对象 obligations 数组中已有的 id；findings[].claim_ids 必须引用本对象 claims 数组中已有的 id。
- 所有 id 必须唯一。没有 obligation、claim 或 finding 时可使用空数组，但不能省略字段。
- 若阶段材料不足，仍输出阶段结果，但使用较低分数、INCONCLUSIVE 结论和 limitations，不能虚构证据。
