from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from backend.app.domain.assets import Asset, DocumentBlock, ParseStatus, ParsedDocument
from backend.app.domain.review_jobs import ReviewJob, ReviewJobStatus
from backend.app.services.automatic_runner import AutomaticReviewRunner, RunStatus
from backend.app.services.stage_orchestrator import StageResult


def make_job():
    return ReviewJob(asset_id="a1", rubric_profile_id="r1", asset_sha256="h1", rubric_source_hash="rh", input_snapshot_hash="ih", state=ReviewJobStatus.EVALUATING)


def make_asset():
    blocks = (DocumentBlock("b1", "a1", "paragraph", "本文内容", page=1, paragraph=1, block_order=0),)
    return Asset("a1", "paper.md", "text/markdown", 10, "h1", ParseStatus.PARSED, __import__('pathlib').Path('paper.md'), ParsedDocument(ParseStatus.PARSED, blocks=blocks))


def make_stage(stage_id, score=8):
    from backend.app.domain.review_protocol import Evidence, EvidenceLevel
    return StageResult(stage_id=stage_id, raw_score_0_10=score, rationale="ok", evidence=[Evidence(id=f"e-{stage_id}", kind="paper", asset_id="a1", block_id="b1", page=1, evidence_level=EvidenceLevel.VERIFIED)])


class Store:
    def __init__(self, job): self.job=job; self.saved=[]
    def get(self, _): return self.job
    def update(self, job): self.job=job; self.saved.append(job); return job
    def save_result_snapshot(self, _, snapshot): self.result=snapshot
    def get_result_snapshot(self, _): return getattr(self, 'result', None)


class Adapter:
    def __init__(self, fail=None): self.calls=[]; self.fail=fail
    def evaluate_stage(self, stage_id, **kwargs):
        self.calls.append(stage_id)
        if stage_id == self.fail: raise RuntimeError("timeout")
        return make_stage(stage_id), SimpleNamespace(model="test", attempts=1, endpoint="http://local")


def test_runner_executes_all_stages_and_aggregates_score():
    store=Store(make_job()); adapter=Adapter()
    runner=AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), adapter)
    result=runner.run("review", run_id="run-1")
    assert adapter.calls == list(runner.stage_ids)
    assert result.run_status is RunStatus.COMPLETED
    assert result.diagnostic_total == pytest.approx(80.0)
    assert result.diagnostic_total_status == "complete"
    assert len(store.saved) >= 7


def test_runner_failure_degrades_and_continues_without_score():
    store=Store(make_job()); adapter=Adapter(fail="assumptions")
    runner=AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), adapter)
    result=runner.run("review", run_id="run-1")
    assert result.run_status is RunStatus.DEGRADED
    assert adapter.calls.index("assumptions") < adapter.calls.index("model_construction")
    assert result.diagnostic_total is None
    assert result.failed_stages == ["assumptions"]
    assert result.stage_runs["assumptions"]["verdict"] == "INCONCLUSIVE"


def test_context_builder_includes_locator_and_truncates():
    store=Store(make_job()); adapter=Adapter()
    runner=AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), adapter, max_context_chars=3)
    context, catalog, meta = runner.build_context("review")
    assert context.startswith("[b1")
    assert "b1" in catalog
    assert meta["context_truncated"] is True


def test_runner_reuses_completed_stages_without_duplicate_weight_and_clears_stale_flag():
    store = Store(make_job()); adapter = Adapter()
    runner = AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), adapter)
    runner.run("review", run_id="run-1")
    adapter.calls.clear()
    rerun = runner.run("review", run_id="run-2", stage_ids=["assumptions"], force_rerun=True)
    assert rerun.completed_stages == list(runner.stage_ids)
    assert len(rerun.completed_stages) == len(set(rerun.completed_stages))
    assert adapter.calls == ["assumptions"]
    assert store.job.state_snapshot["stage_stale"]["assumptions"] is False


def test_runner_rejects_line_locator_mismatch_and_does_not_persist_secret_endpoint():
    from backend.app.domain.review_protocol import Evidence, EvidenceLevel

    class BadLineAdapter:
        def evaluate_stage(self, stage_id, **kwargs):
            result = StageResult(
                stage_id=stage_id,
                raw_score_0_10=8,
                rationale="ok",
                evidence=[Evidence(id="line-mismatch", kind="paper", asset_id="a1", block_id="b1", line_start=99, evidence_level=EvidenceLevel.VERIFIED)],
            )
            return result, SimpleNamespace(model="test", attempts=1, endpoint="https://user:secret@example.test/v1/chat/completions?api_key=secret")

    store = Store(make_job())
    runner = AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), BadLineAdapter())
    result = runner.run("review", run_id="run-1", stage_ids=["problem_identification"], force_rerun=True)
    assert result.run_status is RunStatus.DEGRADED
    assert result.failed_stages == ["problem_identification"]
    assert "secret" not in repr(store.job.state_snapshot)


def test_runner_scrubs_credentials_from_success_metadata():
    class SafeEndpointAdapter(Adapter):
        def evaluate_stage(self, stage_id, **kwargs):
            return make_stage(stage_id), SimpleNamespace(model="test", attempts=1, endpoint="https://user:secret@example.test/v1/chat/completions?api_key=secret")

    store = Store(make_job())
    runner = AutomaticReviewRunner(store, lambda _id: make_asset(), lambda _id: SimpleNamespace(status="published", name="rubric", version="v1", criteria=[]), SafeEndpointAdapter())
    result = runner.run("review", run_id="run-1", stage_ids=["problem_identification"], force_rerun=True)
    assert result.stage_runs["problem_identification"]["endpoint"] == "https://example.test/v1/chat/completions"
    assert "secret" not in repr(store.job.state_snapshot)



