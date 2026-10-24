"""Multi-agent debate panel configuration loader (v0.1).

Pure configuration loading: reads ``config/debate.yaml`` (or a caller-provided
path) and falls back to built-in defaults (fail-open) when the file is missing
or invalid, so a broken config never blocks a review run. This module must not
import ``backend.app.domain.debate`` — the debate domain is wired in later.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


class DebatePanelError(ValueError):
    """Invalid debate panel selection (carries a machine-readable ``code``)."""

    def __init__(self, message: str, *, code: str = "invalid_panel") -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class PanelExpert:
    """One expert seat on the debate panel."""

    id: str
    label: str
    lens: str
    weight: float = 1.0


@dataclass(frozen=True)
class DebateConfig:
    """Validated debate panel configuration (built-in defaults when missing)."""

    experts: tuple[PanelExpert, ...]
    max_rounds: int = 2
    min_rounds: int = 1
    agreement_threshold: float = 0.8
    accept_threshold: float = 0.5
    fatal_bonus: float = 3.0
    max_calls: int = 30
    reject_retry: int = 1
    anonymize: bool = True
    max_opinions_per_expert: int = 8


_DEFAULT_EXPERTS: tuple[PanelExpert, ...] = (
    PanelExpert(id="modeling", label="建模专家", lens="问题识别、假设必要性、模型构造", weight=1.0),
    PanelExpert(id="algorithm", label="算法专家", lens="求解算法适配、收敛性、数值稳定性", weight=1.0),
    PanelExpert(id="statistics", label="统计验证专家", lens="数据质量、验证设计、敏感性分析", weight=1.0),
    PanelExpert(id="code", label="代码审计专家", lens="公式与代码一致性、随机种子、可复现性", weight=1.0),
    PanelExpert(id="writing", label="写作合规专家", lens="结构、表述、引用与竞赛合规", weight=1.0),
)

_ROUND_BOUNDS: tuple[int, int] = (1, 5)


def _coerce_int(value: Any, default: int, *, lo: int, hi: int, field: str) -> int:
    """Clamp a config integer into ``[lo, hi]``; fall back to ``default`` when unusable."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        logger.warning("debate config field %s=%r is not a number; using default %d", field, value, default)
        return default
    return max(lo, min(hi, int(value)))


def _coerce_positive_float(value: Any, default: float, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        logger.warning("debate config field %s=%r is not a number; using default %s", field, value, default)
        return default
    number = float(value)
    if number <= 0:
        logger.warning("debate config field %s=%r must be > 0; using default %s", field, value, default)
        return default
    return number


def _coerce_threshold(value: Any, default: float, field: str) -> float:
    """Clamp a threshold into ``(0, 1]``; unusable values fall back to ``default``."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        logger.warning("debate config field %s=%r is not a number; using default %s", field, value, default)
        return default
    number = float(value)
    if number > 1.0:
        return 1.0
    if number <= 0.0:
        logger.warning("debate config field %s=%r is outside (0, 1]; using default %s", field, value, default)
        return default
    return number


def _coerce_bool(value: Any, default: bool, field: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    logger.warning("debate config field %s=%r is not a boolean; using default %s", field, value, default)
    return default


def _parse_experts(entries: Any) -> tuple[PanelExpert, ...]:
    if entries is None:
        return _DEFAULT_EXPERTS
    if not isinstance(entries, list):
        raise DebatePanelError("panel.experts must be a list", code="invalid_panel")
    experts: list[PanelExpert] = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise DebatePanelError("each panel.experts entry must be a mapping", code="invalid_panel")
        expert_id = str(entry.get("id") or "").strip()
        if not expert_id:
            raise DebatePanelError("each expert requires a non-empty id", code="invalid_panel")
        if expert_id in seen:
            raise DebatePanelError(f"duplicate expert id: {expert_id}", code="invalid_panel")
        seen.add(expert_id)
        experts.append(
            PanelExpert(
                id=expert_id,
                label=str(entry.get("label") or expert_id),
                lens=str(entry.get("lens") or ""),
                weight=_coerce_positive_float(entry.get("weight"), 1.0, "weight"),
            )
        )
    return tuple(experts)


class DebatePanelStore:
    """Load and validate the debate panel configuration from YAML."""

    def __init__(self, root: str | Path | None = None) -> None:
        if root is None:
            # backend/app/services/debate_panel.py -> repo root is parents[3].
            self.config_path: Path = Path(__file__).resolve().parents[3] / "config" / "debate.yaml"
        else:
            self.config_path = Path(root)

    def load(self) -> DebateConfig:
        """Return the configured panel, falling back to built-in defaults (fail-open)."""

        data = self._read_yaml()
        if data is None:
            return DebateConfig(experts=_DEFAULT_EXPERTS)
        try:
            return self._parse(data)
        except DebatePanelError as exc:
            logger.warning("debate config invalid at %s (%s); using built-in defaults", self.config_path, exc)
            return DebateConfig(experts=_DEFAULT_EXPERTS)

    def resolve_experts(self, expert_ids: list[str] | None = None) -> tuple[PanelExpert, ...]:
        """Return all configured experts, or the filtered subset for ``expert_ids``.

        Unknown ids and panels smaller than two experts are rejected with
        ``DebatePanelError`` (code ``invalid_panel``).
        """

        config = self.load()
        if expert_ids is None:
            return config.experts
        known = {expert.id for expert in config.experts}
        unknown = [expert_id for expert_id in expert_ids if expert_id not in known]
        if unknown:
            raise DebatePanelError(f"unknown expert id: {', '.join(unknown)}", code="invalid_panel")
        wanted = set(expert_ids)
        selected = tuple(expert for expert in config.experts if expert.id in wanted)
        if len(selected) < 2:
            raise DebatePanelError("at least 2 experts are required for a debate", code="invalid_panel")
        return selected

    def _read_yaml(self) -> Any | None:
        try:
            text = self.config_path.read_text(encoding="utf-8")
        except OSError as exc:
            logger.warning("debate config unavailable at %s (%s); using built-in defaults", self.config_path, exc)
            return None
        try:
            return yaml.safe_load(text)
        except yaml.YAMLError as exc:
            logger.warning("debate config unreadable at %s (%s); using built-in defaults", self.config_path, exc)
            return None

    @staticmethod
    def _parse(data: Any) -> DebateConfig:
        if not isinstance(data, dict):
            raise DebatePanelError("config root must be a mapping", code="invalid_panel")
        panel = data.get("panel")
        debate = data.get("debate")
        if panel is not None and not isinstance(panel, dict):
            raise DebatePanelError("panel section must be a mapping", code="invalid_panel")
        if debate is not None and not isinstance(debate, dict):
            raise DebatePanelError("debate section must be a mapping", code="invalid_panel")
        panel = panel or {}
        debate = debate or {}

        experts = _parse_experts(panel.get("experts"))

        max_rounds = _coerce_int(
            debate.get("max_rounds"), 2, lo=_ROUND_BOUNDS[0], hi=_ROUND_BOUNDS[1], field="max_rounds"
        )
        min_rounds = _coerce_int(
            debate.get("min_rounds"), 1, lo=_ROUND_BOUNDS[0], hi=max_rounds, field="min_rounds"
        )
        if min_rounds > max_rounds:
            min_rounds = max_rounds

        return DebateConfig(
            experts=experts,
            max_rounds=max_rounds,
            min_rounds=min_rounds,
            agreement_threshold=_coerce_threshold(
                debate.get("agreement_threshold"), 0.8, "agreement_threshold"
            ),
            accept_threshold=_coerce_threshold(debate.get("accept_threshold"), 0.5, "accept_threshold"),
            fatal_bonus=_coerce_positive_float(debate.get("fatal_bonus"), 3.0, "fatal_bonus"),
            max_calls=_coerce_int(debate.get("max_calls"), 30, lo=1, hi=10000, field="max_calls"),
            reject_retry=_coerce_int(debate.get("reject_retry"), 1, lo=0, hi=10, field="reject_retry"),
            anonymize=_coerce_bool(debate.get("anonymize"), True, "anonymize"),
            max_opinions_per_expert=_coerce_int(
                debate.get("max_opinions_per_expert"), 8, lo=1, hi=100, field="max_opinions_per_expert"
            ),
        )


__all__ = [
    "DebateConfig",
    "DebatePanelError",
    "DebatePanelStore",
    "PanelExpert",
]
