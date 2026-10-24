"""Tests for the debate prompt assets and PromptTemplateStore.debate_prompt."""

from __future__ import annotations

import pytest

from backend.app.services.prompt_templates import PromptBundle, PromptTemplateError, PromptTemplateStore


def test_panel_opinion_bundle_has_debate_stage_id() -> None:
    store = PromptTemplateStore()
    bundle = store.debate_prompt("panel_opinion", expert_lens="建模专家透镜")
    assert isinstance(bundle, PromptBundle)
    assert bundle.version == "v0.1"
    assert bundle.stage_id == "debate:panel_opinion"
    assert "建模专家透镜" in bundle.user
    assert "只输出严格 JSON" in bundle.system


def test_both_debate_kinds_exist() -> None:
    store = PromptTemplateStore()
    for kind, stage_id in (
        ("panel_opinion", "debate:panel_opinion"),
        ("debate_message", "debate:debate_message"),
    ):
        bundle = store.debate_prompt(kind)
        assert bundle.stage_id == stage_id
        assert bundle.system
        assert "{{" not in bundle.user


def test_message_placeholders_render_from_values() -> None:
    store = PromptTemplateStore()
    bundle = store.debate_prompt(
        "debate_message",
        round_number="2",
        opinions_json='[{"opinion_id": "op-0-modeling-1"}]',
        previous_messages_json="[]",
        own_expert_id="exp-anon-1",
        known_evidence_ids="ev-1, ev-2",
        expert_lens="代码审计专家透镜",
    )
    assert "exp-anon-1" in bundle.user
    assert "代码审计专家透镜" in bundle.user
    assert 'op-0-modeling-1' in bundle.user
    assert "ev-1, ev-2" in bundle.user
    assert "{{" not in bundle.user


def test_missing_values_are_filled_safely() -> None:
    store = PromptTemplateStore()
    bundle = store.debate_prompt("panel_opinion")
    assert "{{" not in bundle.user
    assert "（未提供）" in bundle.user

    message = store.debate_prompt("debate_message")
    assert "{{" not in message.user
    assert "[]" in message.user  # opinions_json / previous_messages_json defaults


def test_unknown_kind_is_rejected() -> None:
    store = PromptTemplateStore()
    with pytest.raises(PromptTemplateError):
        store.debate_prompt("nope")
