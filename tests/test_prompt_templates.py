import pytest

from backend.app.services.prompt_templates import PromptTemplateError, PromptTemplateStore


def test_stage_prompt_renders_context_and_schema() -> None:
    bundle = PromptTemplateStore().stage_prompt(
        "model_construction",
        paper_context="paper-block-1",
        evidence_catalog="evidence-1",
    )
    assert bundle.version == "v0.1"
    assert "paper-block-1" in bundle.user
    assert "model_construction" in bundle.user
    assert '"raw_score_0_10"' in bundle.user
    assert "INCONCLUSIVE" in bundle.system


def test_unknown_stage_or_auxiliary_prompt_is_rejected() -> None:
    store = PromptTemplateStore()
    with pytest.raises(PromptTemplateError):
        store.stage_prompt("unknown")
    with pytest.raises(PromptTemplateError):
        store.auxiliary_prompt("unknown")
