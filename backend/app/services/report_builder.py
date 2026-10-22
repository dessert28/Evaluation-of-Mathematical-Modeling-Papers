from __future__ import annotations

import json
from typing import Any

from backend.app.domain.review_results import ReviewResult


class ReportBuilder:
    def __init__(self, result_service: Any):
        self.result_service = result_service

    def load(self, review_id: str) -> ReviewResult:
        result = self.result_service.load(review_id)
        if result is None:
            raise ValueError("review result not found")
        return result

    def as_json(self, review_id: str) -> dict[str, Any]:
        return self.load(review_id).to_snapshot()

    def as_markdown(self, review_id: str) -> str:
        result = self.load(review_id)
        metadata = result.metadata or {}
        model = metadata.get("model_metadata") or {}
        lines = [f"# 数学建模论文评审报告", "", f"- 评审任务：`{result.review_id}`", f"- 运行状态：`{metadata.get('run', {}).get('run_status', 'unknown')}`", f"- 模型提供商：`{model.get('provider', 'unknown')}`", f"- 模型名称：`{model.get('model', 'unknown')}`", ""]
        lines += ["## 通用诊断评分", ""]
        if result.diagnostic_scores:
            lines.append("| 阶段 | 原始分 | 归一化分 | 权重 | 证据 |")
            lines.append("|---|---:|---:|---:|---:|")
            for score in result.diagnostic_scores:
                lines.append(f"| {score.criterion} | {score.raw_score_0_10:.2f} | {score.normalized_score_0_4:.2f} | {score.weight:.2f} | {len(score.evidence_ids)} |")
        else:
            lines.append("暂无完整诊断评分。")
        lines += ["", "## 官方评分", ""]
        if result.official_scores:
            for score in result.official_scores:
                lines.append(f"- {score.criterion}: {score.raw_score_0_10:.2f}")
        else:
            lines.append("暂无已确认的官方评分。")
        lines += ["", "## Findings", ""]
        for finding in result.findings:
            lines.append(f"- **[{finding.severity.value}] {finding.title}**（{finding.verdict.value}）：{finding.detail or ''}")
        if not result.findings:
            lines.append("暂无问题记录。")
        lines += ["", "## 优化建议", ""]
        for recommendation in result.recommendations:
            lines.append(f"- **{recommendation.priority.value}** {recommendation.action}；验收：{recommendation.acceptance}")
        if not result.recommendations:
            lines.append("暂无优化建议。")
        lines += ['', '## 主张与验证义务', '']
        for claim in result.claims:
            lines.append(f'- `{claim.id}` [{claim.verdict.value}] {claim.exact_text}')
            if claim.scope:
                lines.append(f'  - 适用范围：{claim.scope}')
            for obligation in result.obligations:
                if obligation.id in claim.obligation_ids:
                    status = '待核验' if obligation.fulfilled is None else '满足' if obligation.fulfilled else '未满足'
                    lines.append(f'  - 义务 `{obligation.id}`：{obligation.text}（{status}）；证据：{", ".join(obligation.evidence_ids) or "待人工核实"}')
            lines.append(f'  - 主张证据：{", ".join(claim.evidence_ids) or "待人工核实"}')
        lines += ['', '## 人工修改记录', '']
        for edit in metadata.get('recommendation_edit_history', []):
            lines.append(f'- `{edit.get("recommendation_id")}` · {edit.get("decided_at")} · {edit.get("decided_by")}：{edit.get("rationale")}')
            lines.append(f'  - 原动作：{edit.get("before", {}).get("action", "")}')
            lines.append(f'  - 新动作：{edit.get("after", {}).get("action", "")}')
        if not metadata.get('recommendation_edit_history'):
            lines.append('暂无人工修改记录。')
        if metadata.get('recommendation_archive'):
            lines += ['', '## 待重新核对的人工建议', '', '重跑后的证据引用已变化，以下人工内容仅供核对，不作为当前有效建议。']
            for item in metadata['recommendation_archive'].values():
                lines.append(f'- {item["action"]}；验收：{item["acceptance"]}')
        lines += ["", "## 证据索引", ""]
        for evidence in result.evidence:
            location = ", ".join(f"{key}={value}" for key, value in evidence.location.items()) or "待人工核实"
            lines.append(f"- `{evidence.id}`（{evidence.evidence_level.value}）：{location}")
        return "\n".join(lines) + "\n"
