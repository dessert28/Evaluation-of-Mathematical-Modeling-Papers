"""Real API contracts needed by the redesigned frontend."""
import json
from pathlib import Path

from fastapi.testclient import TestClient
from backend.app.main import create_app
from backend.app.settings import Settings


def test_rubric_json_file_registers_source_and_can_publish(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    content = json.dumps({"name": "官方量表", "version": "v1", "criteria": [
        {"id": "model", "label": "模型", "weight": 1, "scale_min": 0, "scale_max": 100}
    ]}).encode()
    imported = client.post('/api/v1/rubrics/import', files={'file': ('rubric.json', content, 'application/json')})
    assert imported.status_code == 201, imported.text
    draft = imported.json()
    source = client.get('/api/v1/assets/' + draft['source_asset_id']).json()
    assert source['sha256'] == draft['source_hash']
    assert source['filename'] == 'rubric.json'
    assert source['status'] == 'parsed'
    published = client.post('/api/v1/rubrics/' + draft['id'] + '/publish', json={
        'confirmed_by': 'human', 'decision': 'publish', 'rationale': '人工核对了全部条目'
    })
    assert published.status_code == 200


def test_rubric_markdown_file_registers_source(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    content = b'# Rubric\n| id | label | weight |\n|---|---|---|\n| model | Model | 1 |\n'
    response = client.post('/api/v1/rubrics/import', files={'file': ('rubric.md', content, 'text/markdown')})
    assert response.status_code == 201, response.text
    draft = response.json()
    assert client.get('/api/v1/assets/' + draft['source_asset_id'] + '/blocks').json()


def test_bad_rubric_file_is_readable_error(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    for payload in (b'', b'{invalid json'):
        response = client.post('/api/v1/rubrics/import', files={'file': ('bad.json', payload, 'application/json')})
        assert response.status_code == 422
        assert response.json()['error']['code'] in {'empty_file', 'parse_failed'}


def test_model_edit_activation_and_connection_failure_hide_credentials(tmp_path: Path, monkeypatch):
    import httpx

    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    secret = 'frontend-contract-secret'
    body = {'provider': 'custom', 'base_url': 'https://example.test/v1',
            'api_key': secret, 'model': 'first', 'is_active': True}
    first = client.post('/api/v1/model-config', json=body).json()
    second = client.post('/api/v1/model-config', json={**body, 'model': 'second'}).json()
    edited = client.put('/api/v1/model-config/' + first['id'],
                        json={**body, 'api_key': '', 'model': 'edited'})
    assert edited.status_code == 200
    assert edited.json()['api_key_configured'] is True
    items = client.get('/api/v1/model-config').json()['items']
    assert [item['id'] for item in items if item['is_active']] == [first['id']]

    original_post = httpx.Client.post

    def fail_connection(self, url, *args, **kwargs):
        if str(url) == 'https://example.test/v1/chat/completions':
            assert kwargs['headers']['Authorization'] == 'Bearer ' + secret
            raise httpx.ConnectError(secret)
        return original_post(self, url, *args, **kwargs)

    monkeypatch.setattr(httpx.Client, 'post', fail_connection)
    tested = client.post('/api/v1/model-config/' + first['id'] + '/test')
    assert tested.status_code == 502
    assert secret not in tested.text
    assert secret not in edited.text
    assert secret not in client.get('/api/v1/model-config').text
    assert client.delete('/api/v1/model-config/' + second['id']).status_code == 200
    assert client.delete('/api/v1/model-config/' + first['id']).status_code == 200
    assert client.get('/api/v1/model-config').json()['items'] == []


def test_rubric_edits_require_bound_hash_and_published_version_is_immutable(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    content = {'name': 'Bound rubric', 'version': 'v1', 'criteria': [
        {'id': 'model', 'label': 'Model', 'weight': 1}]}
    response = client.post('/api/v1/rubrics/import', files={
        'file': ('bound.json', json.dumps(content).encode(), 'application/json')})
    assert response.status_code == 201
    draft = response.json()
    body = {'format': 'json', 'source_asset_id': draft['source_asset_id'],
            'source_hash': draft['source_hash'], 'content': content}
    path = '/api/v1/rubrics/' + draft['id']
    mismatch = client.put(path, json={**body, 'source_hash': '0' * 64})
    assert mismatch.status_code == 409
    assert mismatch.json()['error']['code'] == 'source_hash_mismatch'
    assert client.put(path, json=body).status_code == 200
    assert client.post(path + '/publish', json={
        'confirmed_by': 'human', 'rationale': 'Checked criteria', 'decision': 'publish'}).status_code == 200
    assert client.put(path, json=body).status_code == 409


def test_failed_paper_upload_remains_available_for_inspection(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    failed = client.post('/api/v1/assets', files={'file': ('empty.md', b'', 'text/markdown')})
    assert failed.status_code == 422
    assets = client.get('/api/v1/assets').json()
    assert len(assets) == 1
    assert assets[0]['status'] == 'failed'
    assert assets[0]['error_code'] == 'empty_file'
    assert client.get('/api/v1/assets/' + assets[0]['id']).json()['status'] == 'failed'
    assert client.get('/api/v1/assets/' + assets[0]['id'] + '/blocks').json() == []


def test_model_validation_error_does_not_echo_oversized_key(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    secret = 'sensitive-api-key-' + 'x' * 4001
    response = client.post('/api/v1/model-config', json={
        'provider': 'custom', 'base_url': 'https://example.test/v1',
        'api_key': secret, 'model': 'demo', 'is_active': True})
    assert response.status_code == 422
    assert secret not in response.text
    assert 'sensitive-api-key-' not in response.text


def test_credential_urls_are_rejected_without_reflection(tmp_path: Path):
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.post('/api/v1/model-config', json={
        'provider': 'custom', 'base_url': 'https://secret-user:secret-password@example.test/v1?key=secret-query',
        'api_key': '', 'model': 'demo', 'is_active': True})
    assert response.status_code == 422
    assert 'secret-password' not in response.text
    assert 'secret-query' not in response.text


def test_connection_test_rejects_invalid_json_with_runtime_endpoint_rules(tmp_path: Path, monkeypatch):
    import httpx
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    config = client.post('/api/v1/model-config', json={
        'provider': 'custom', 'base_url': 'https://example.test', 'api_key': '',
        'model': 'demo', 'is_active': True}).json()
    original_post = httpx.Client.post
    def fake(self, url, *args, **kwargs):
        if str(url) == 'https://example.test/v1/chat/completions':
            return httpx.Response(200, json={'choices': [{'message': {'content': 'not json'}}]})
        return original_post(self, url, *args, **kwargs)
    monkeypatch.setattr(httpx.Client, 'post', fake)
    response = client.post('/api/v1/model-config/' + config['id'] + '/test')
    assert response.status_code == 502
    assert response.json()['error']['code'] == 'model_response_invalid'


def test_unbuilt_frontend_has_safe_startup_page(tmp_path: Path, monkeypatch):
    original = Path.is_dir
    def is_dir(path):
        return False if path.parts[-2:] == ('frontend', 'dist') else original(path)
    monkeypatch.setattr(Path, 'is_dir', is_dir)
    client = TestClient(create_app(Settings(data_dir=tmp_path)))
    response = client.get('/')
    assert response.status_code == 200
    assert 'npm run build --prefix frontend' in response.text
    assert '<script' not in response.text
