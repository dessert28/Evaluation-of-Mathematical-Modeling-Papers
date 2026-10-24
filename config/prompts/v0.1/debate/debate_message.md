# 辩论发言（第 {{ round_number }} 轮）

你以「{{ expert_lens }}」的专家透镜参与评审委员会辩论，你的匿名标识是 `{{ own_expert_id }}`。

当前意见集（JSON 数组）：

{{ opinions_json }}

历史发言（JSON 数组）：

{{ previous_messages_json }}

你已知晓的证据 id 目录：

{{ known_evidence_ids }}

任务：

针对意见集中其他专家（以及你自己的）既有意见，逐条选择是否表态。允许对部分意见保持沉默（不输出对应发言）。立场含义：

- `AGREE`：认同该意见，可补充新证据或新的定位信息；
- `QUALIFY`：部分认同，指出其适用范围、前提或证据缺口；
- `DISAGREE`：不认同其结论，说明原因（没有直接反证时使用，并注明缺失什么证据）；
- `REFUTE`：用真实证据直接反驳该意见；
- `WITHDRAW`：撤回你自己提出的意见。

只输出一个 JSON 对象，字段名必须与下面结构完全一致（可选字段不修订时填 `null`）：

{
  "messages": [
    {
      "target_opinion_id": "op-0-modeling-1",
      "stance": "QUALIFY",
      "evidence_ids": ["evidence-unique-id"],
      "confidence": 0.7,
      "rationale": "基于证据的具体说明",
      "revised_title": null,
      "revised_detail": null,
      "revised_severity": null
    }
  ]
}

约束：

- `stance` 只能取 `AGREE`、`QUALIFY`、`DISAGREE`、`REFUTE`、`WITHDRAW`。
- `REFUTE` 必须引用真实证据 id：`evidence_ids` 至少 1 条，且必须来自上面的证据 id 目录；没有证据不得反驳。
- `WITHDRAW` 仅用于撤回你自己提出的意见，不得用于他人意见。
- 每条发言必须包含 `target_opinion_id`、`stance`、`evidence_ids`、`confidence`、`rationale`；`revised_title`、`revised_detail`、`revised_severity` 为可选，仅在你认为原意见应被修订时填写，`revised_severity` 仍须取自 `MINOR`/`MODERATE`/`MAJOR`/`FATAL`。
- `target_opinion_id` 必须来自上面的意见集。
- 不要重复他人已用相同证据说明过的论据；如完全认同，使用 `AGREE`，必要时补充新证据或新定位。
- 对事不对人，措辞中性、具体、可复核；`confidence` 为 0 到 1 的数字，证据不足时必须降低。
- 没有需要表态的意见时输出空数组 `[]`。
