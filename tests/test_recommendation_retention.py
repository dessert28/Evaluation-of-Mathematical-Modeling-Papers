from backend.app.domain.review_protocol import Finding, Recommendation
from backend.app.domain.review_results import ReviewResult
from backend.app.services.recommendation_edits import RecommendationEditService
from backend.app.services.review_results import ReviewResultService


class Store:
    def __init__(self):
        self.result = ReviewResult(review_id='r1', findings=[Finding(id='f1', title='检查', severity='minor')],
                                   recommendations=[Recommendation(id='s1', finding_id='f1', action='原始动作', acceptance='原始验收')]).to_snapshot()
        self.decisions = []

    def get_result_snapshot(self, review_id): return self.result
    def save_result_snapshot(self, review_id, result): self.result = result
    def save_decision(self, decision): self.decisions.append(decision)


def test_human_recommendation_and_original_survive_model_rerun():
    store = Store()
    RecommendationEditService(store).update('r1', 's1', action='人工动作', acceptance='人工验收',
                                           priority='major', owner='作者', decided_by='human', rationale='核对后修改')
    new = ReviewResult(review_id='r1', findings=[Finding(id='f1', title='重跑检查', severity='minor')],
                       recommendations=[Recommendation(id='s1', finding_id='f1', action='模型覆盖动作', acceptance='模型验收')])
    saved = ReviewResultService(store).save(new)
    assert saved.recommendations[0].action == '人工动作'
    assert saved.metadata['recommendation_originals']['s1']['action'] == '原始动作'
    assert saved.metadata['recommendation_edit_history'][0]['after']['action'] == '人工动作'


def test_missing_evidence_dependencies_archive_human_text_instead_of_fabricating_links():
    store = Store()
    RecommendationEditService(store).update('r1', 's1', action='人工动作', acceptance='人工验收',
                                           priority='major', owner=None, decided_by='human', rationale='修改理由')
    saved = ReviewResultService(store).save(ReviewResult(review_id='r1'))
    assert saved.recommendations == []
    assert saved.metadata['recommendation_archive']['s1']['action'] == '人工动作'


def test_reused_model_id_cannot_impersonate_archived_human_text_and_restore_is_possible():
    store = Store()
    RecommendationEditService(store).update('r1', 's1', action='人工动作', acceptance='人工验收',
                                           priority='major', owner=None, decided_by='human', rationale='修改理由')
    service = ReviewResultService(store)
    service.save(ReviewResult(review_id='r1'))
    unrelated = service.save(ReviewResult(review_id='r1', findings=[Finding(id='f2', title='新问题', severity='minor')],
                             recommendations=[Recommendation(id='s1', finding_id='f2', action='冒用相同ID的模型建议', acceptance='验收')]))
    assert unrelated.recommendations == []
    restored = service.save(ReviewResult(review_id='r1', findings=[Finding(id='f1', title='原问题重新绑定', severity='minor')],
                            recommendations=[Recommendation(id='s1', finding_id='f1', action='模型动作', acceptance='验收')]))
    assert restored.recommendations[0].action == '人工动作'
    assert restored.metadata['recommendation_archive'] == {}
