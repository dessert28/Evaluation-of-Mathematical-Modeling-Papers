"""Tests for the debate panel configuration loader (v0.1 iteration 2a)."""

from __future__ import annotations

from pathlib import Path

import pytest

from backend.app.services.debate_panel import DebatePanelError, DebatePanelStore


VALID_YAML = """
schema_version: 1
panel:
  experts:
    - id: modeling
      label: 建模专家
      lens: 问题识别、假设必要性、模型构造
      weight: 1.0
    - id: algorithm
      label: 算法专家
      lens: 求解算法适配、收敛性、数值稳定性
      weight: 1.5
debate:
  max_rounds: 2
  min_rounds: 1
  agreement_threshold: 0.8
  accept_threshold: 0.5
  fatal_bonus: 3.0
  max_calls: 30
  reject_retry: 1
  anonymize: true
  max_opinions_per_expert: 8
"""


def _store(tmp_path: Path, content: str, name: str = "debate.yaml") -> DebatePanelStore:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return DebatePanelStore(path)


def test_load_parses_experts_and_debate_fields(tmp_path: Path) -> None:
    config = _store(tmp_path, VALID_YAML).load()
    assert [expert.id for expert in config.experts] == ["modeling", "algorithm"]
    assert config.experts[0].label == "建模专家"
    assert config.experts[0].lens == "问题识别、假设必要性、模型构造"
    assert config.experts[0].weight == 1.0
    assert config.experts[1].weight == 1.5
    assert config.max_rounds == 2
    assert config.min_rounds == 1
    assert config.agreement_threshold == 0.8
    assert config.accept_threshold == 0.5
    assert config.fatal_bonus == 3.0
    assert config.max_calls == 30
    assert config.reject_retry == 1
    assert config.anonymize is True
    assert config.max_opinions_per_expert == 8


def test_default_root_loads_repo_config() -> None:
    config = DebatePanelStore().load()
    assert [expert.id for expert in config.experts] == [
        "modeling",
        "algorithm",
        "statistics",
        "code",
        "writing",
    ]
    assert all(expert.weight == 1.0 for expert in config.experts)
    assert config.max_rounds == 2
    assert config.anonymize is True


def test_resolve_experts_defaults_and_filters(tmp_path: Path) -> None:
    store = _store(tmp_path, VALID_YAML)
    assert [expert.id for expert in store.resolve_experts()] == ["modeling", "algorithm"]
    # Requested order is normalized to the configured panel order.
    assert [expert.id for expert in store.resolve_experts(["algorithm", "modeling"])] == ["modeling", "algorithm"]


def test_resolve_experts_rejects_unknown_id(tmp_path: Path) -> None:
    store = _store(tmp_path, VALID_YAML)
    with pytest.raises(DebatePanelError) as excinfo:
        store.resolve_experts(["modeling", "ghost"])
    assert isinstance(excinfo.value, ValueError)
    assert excinfo.value.code == "invalid_panel"
    assert "ghost" in str(excinfo.value)


def test_resolve_experts_rejects_fewer_than_two(tmp_path: Path) -> None:
    store = _store(tmp_path, VALID_YAML)
    with pytest.raises(DebatePanelError):
        store.resolve_experts(["modeling"])


def test_missing_file_falls_back_to_builtin_defaults(tmp_path: Path) -> None:
    store = DebatePanelStore(tmp_path / "does-not-exist.yaml")
    config = store.load()
    assert [expert.id for expert in config.experts] == [
        "modeling",
        "algorithm",
        "statistics",
        "code",
        "writing",
    ]
    assert config.max_rounds == 2
    assert config.agreement_threshold == 0.8
    assert config.accept_threshold == 0.5
    assert config.max_opinions_per_expert == 8


def test_invalid_file_falls_back_to_builtin_defaults(tmp_path: Path) -> None:
    for content in ("panel: [unclosed", "42\n", "not a mapping: {",):
        config = _store(tmp_path, content).load()
        assert [expert.id for expert in config.experts] == [
            "modeling",
            "algorithm",
            "statistics",
            "code",
            "writing",
        ]
        assert config.max_rounds == 2


def test_max_rounds_clamped_to_bounds(tmp_path: Path) -> None:
    too_many = VALID_YAML.replace("max_rounds: 2", "max_rounds: 9")
    assert _store(tmp_path, too_many).load().max_rounds == 5

    zero = VALID_YAML.replace("max_rounds: 2", "max_rounds: 0")
    assert _store(tmp_path, zero).load().max_rounds == 1


def test_thresholds_clamped_to_unit_interval(tmp_path: Path) -> None:
    content = VALID_YAML.replace("agreement_threshold: 0.8", "agreement_threshold: 1.5").replace(
        "accept_threshold: 0.5", "accept_threshold: -0.2"
    )
    config = _store(tmp_path, content).load()
    assert config.agreement_threshold == 1.0
    # accept_threshold <= 0 falls back to the built-in default.
    assert config.accept_threshold == 0.5


def test_non_positive_expert_weight_falls_back(tmp_path: Path) -> None:
    content = VALID_YAML.replace("weight: 1.0", "weight: 0")
    config = _store(tmp_path, content).load()
    assert config.experts[0].weight == 1.0
