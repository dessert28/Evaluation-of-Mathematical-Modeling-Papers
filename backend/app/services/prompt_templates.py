"""Versioned prompt assets for the optional OpenAI-compatible evaluator."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


class PromptTemplateError(ValueError):
    pass


_DEBATE_KINDS: frozenset[str] = frozenset({"panel_opinion", "debate_message"})

# Friendly fallbacks for debate-template placeholders the caller does not fill.
_DEBATE_PLACEHOLDER_DEFAULTS: Mapping[str, str] = {
    "paper_context": "（未提供）",
    "evidence_catalog": "（未提供）",
    "rubric_context": "（未提供）",
    "stage_results_summary": "（无）",
    "expert_lens": "（未指定，使用通用评审视角）",
    "max_opinions": "8",
    "round_number": "1",
    "opinions_json": "[]",
    "previous_messages_json": "[]",
    "own_expert_id": "（未指定）",
    "known_evidence_ids": "（未提供）",
}

_DEBATE_PLACEHOLDER_RE = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


_STAGE_META: Mapping[str, tuple[str, str]] = {
    "problem_identification": ("问题识别", "objective_coverage, subproblem_coverage, constraint_identification"),
    "problem_formulation": ("问题表述", "variables, symbols, units, constraints"),
    "assumptions": ("假设建立", "necessity, rationale, boundary, counterfactual_risk"),
    "model_construction": ("模型构造", "model_problem_fit, equation_closure, objective, alternative_models"),
    "solving": ("模型求解", "algorithm_fit, convergence, numerical_stability, reproducibility"),
    "code_implementation": ("代码实现", "formula_implementation_consistency, dependencies, seed, input_output_contract"),
    "results_analysis": ("结果分析", "back_substitution, baseline, sensitivity, robustness, claim_scope"),
}


@dataclass(frozen=True)
class PromptBundle:
    version: str
    stage_id: str
    system: str
    user: str


class PromptTemplateStore:
    """Load prompt files from the project so they can be reviewed and versioned."""

    def __init__(self, root: str | Path | None = None, *, version: str = "v0.1") -> None:
        default_root = Path(__file__).resolve().parents[3] / "config" / "prompts"
        self.root = Path(root) if root is not None else default_root
        self.version = version

    @property
    def version_root(self) -> Path:
        return self.root / self.version

    def _read(self, relative: str) -> str:
        path = self.version_root / relative
        try:
            return path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptTemplateError(f"prompt template unavailable: {path}") from exc

    @staticmethod
    def _render(template: str, values: Mapping[str, str]) -> str:
        rendered = template
        for key, value in values.items():
            rendered = rendered.replace("{{ " + key + " }}", value)
        return rendered

    def system_prompt(self) -> str:
        return self._read("system.md")

    def stage_prompt(
        self,
        stage_id: str,
        *,
        paper_context: str = "（未提供）",
        evidence_catalog: str = "（未提供）",
        rubric_context: str = "（未提供）",
        prior_results: str = "（无）",
    ) -> PromptBundle:
        if stage_id not in _STAGE_META:
            raise PromptTemplateError(f"unknown diagnostic stage: {stage_id}")
        stage_name, checks = _STAGE_META[stage_id]
        common = self._render(
            self._read("stage_common.md"),
            {
                "stage_id": stage_id,
                "stage_name": stage_name,
                "paper_context": paper_context,
                "evidence_catalog": evidence_catalog,
                "rubric_context": rubric_context,
                "prior_results": prior_results,
                "checks": checks,
            },
        )
        stage = self._render(self._read(f"stages/{stage_id}.md"), {"common": common})
        return PromptBundle(version=self.version, stage_id=stage_id, system=self.system_prompt(), user=stage)

    def auxiliary_prompt(self, name: str, **values: str) -> str:
        if name not in {"evidence_audit", "recommendations", "arbitration"}:
            raise PromptTemplateError(f"unknown auxiliary prompt: {name}")
        return self._render(self._read(f"{name}.md"), values)

    def debate_prompt(self, kind: str, **values) -> PromptBundle:
        """Render a multi-agent debate prompt (Round 0 opinion or Round ≥1 message).

        Placeholders missing from ``values`` are filled with a friendly default
        (see ``_DEBATE_PLACEHOLDER_DEFAULTS``) instead of leaking raw ``{{ key }}``
        tokens into the rendered prompt.
        """
        if kind not in _DEBATE_KINDS:
            raise PromptTemplateError(f"unknown debate prompt kind: {kind}")
        system = self._read("debate/system.md")
        user = self._render(self._read(f"debate/{kind}.md"), values)
        user = _DEBATE_PLACEHOLDER_RE.sub(
            lambda match: _DEBATE_PLACEHOLDER_DEFAULTS.get(match.group(1), ""),
            user,
        )
        return PromptBundle(version=self.version, stage_id=f"debate:{kind}", system=system, user=user)


__all__ = ["PromptBundle", "PromptTemplateError", "PromptTemplateStore"]
