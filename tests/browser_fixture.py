"""Isolated local mock cloud for browser acceptance. Never use this in production.

Start with uvicorn tests.browser_fixture:create_fixture --factory --port 8027.
All data lives in a fresh ignored .tmp directory. The actual adapter, SQLite,
asset importer, coordinator and seven-stage runner are used unmodified.
"""
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from backend.app.main import create_app
from backend.app.settings import Settings
from backend.app.domain.review_protocol import Claim, Evidence, Finding, Obligation
from backend.app.services.stage_orchestrator import StageResult


def create_fixture():
    settings = Settings(data_dir=Path('.tmp') / f'browser-fixture-{uuid4().hex}',
                        llm_timeout_seconds=15, llm_max_retries=0)
    app = create_app(settings)
    static_mount = app.router.routes.pop()

    @app.post('/mock/v1/chat/completions')
    def mock_cloud(request: Request, body: dict):
        user = body.get('messages', [{}])[-1].get('content', '')
        system = body.get('messages', [{}])[0].get('content', '') if len(body.get('messages', [])) >= 1 else ''
        if 'Return JSON' in user:
            content = {'ok': True}
        elif '"MessageDraft"' in system:
            # Multi-agent debate, rounds 1..n: every expert agrees so the panel
            # converges on the first exchange round.
            content = {'messages': [{
                'target_opinion_id': 'op-0-expert-1-0', 'stance': 'AGREE',
                'evidence_ids': [], 'confidence': 0.6, 'rationale': '同意该意见（模拟辩论）',
            }]}
            time.sleep(.4)
        elif '"OpinionDraft"' in system:
            # Multi-agent debate, round 0: each expert returns a structured
            # opinion that anchors on one of the job's own evidence ids so the
            # engine's evidence checks pass and the debate can converge fast.
            jobs = app.state.review_job_repository.list()
            if not jobs:
                return {'choices': [{'message': {'role': 'assistant', 'content': json.dumps(
                    {'opinions': []}, ensure_ascii=False)}}]}
            job = jobs[0]
            snapshot = dict(job.state_snapshot or {})
            evidence_id = None
            for result in (snapshot.get('stage_results') or {}).values():
                evidence = (result or {}).get('evidence') or []
                if evidence:
                    evidence_id = evidence[0].get('id') or evidence[0].get('evidence_id')
                    break
            if evidence_id is None:
                return {'choices': [{'message': {'role': 'assistant', 'content': json.dumps(
                    {'opinions': []}, ensure_ascii=False)}}]}
            content = {'opinions': [{
                'stage_id': 'model_construction', 'title': '目标函数缺少闭环约束（模拟辩论）',
                'detail': '测试夹具：仅用于界面验收，不代表论文实际评价。', 'severity': 'major',
                'evidence_ids': [evidence_id], 'confidence': 0.7,
            }]}
            time.sleep(.4)
        else:
            match = re.search(r'评审阶段：`?(\w+)`?', user)
            stage = match.group(1)
            job = app.state.review_job_repository.list()[0]
            asset = app.state.asset_store.get(job.asset_id)
            block = asset.blocks[0]
            evidence_id = f'evidence-{stage}'
            claim_id = f'claim-{stage}'
            obligation_id = f'obligation-{stage}'
            evidence = Evidence(id=evidence_id, kind='document', asset_id=asset.id,
                                block_id=block.block_id, page=block.page, paragraph=block.paragraph,
                                line_start=block.line_start, line_end=block.line_end,
                                evidence_level='VERIFIED', limitations=['模拟模型，仅用于界面验收'])
            obligation = Obligation(id=obligation_id, text='检查论文是否给出验证方法',
                                    fulfilled=True, evidence_ids=[evidence_id])
            claim = Claim(id=claim_id, exact_text='论文描述了验证方法（模拟评审）',
                          verdict='SUPPORTED', obligation_ids=[obligation_id], evidence_ids=[evidence_id])
            finding = Finding(id=f'finding-{stage}', title='补充独立验证（模拟评审）',
                              detail='测试夹具：检查证据定位与建议编辑，不代表论文实际评价。',
                              severity='minor', claim_ids=[claim_id], evidence_ids=[evidence_id])
            content = StageResult(stage_id=stage, raw_score_0_10=8,
                                  rationale='模拟模型验证接口契约', evidence=[evidence],
                                  obligations=[obligation], claims=[claim], findings=[finding]).model_dump(mode='json')
            time.sleep(.5)
        return {'choices': [{'message': {'role': 'assistant', 'content': json.dumps(content, ensure_ascii=False)}}]}

    app.router.routes.append(static_mount)
    return app
