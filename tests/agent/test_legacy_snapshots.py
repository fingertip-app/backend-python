"""Pin the public behavior of existing routes while new schemas are introduced."""
import json
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.api.v1.routers import ai
from app.core.config import settings
from app.main import app
from tests.conftest import HealthyDb

SNAPSHOT = json.loads(Path('docs/contracts/agent-v1/legacy-endpoints.json').read_text())

class ExplainProvider:
    def explain(self, db, query, locale):
        return {'answer': '전통 문화 설명', 'sources': [{'id': 9001, 'name': '합성 판소리', 'source': 'synthetic://legacy', 'category': '음악'}], 'matchingKeywords': ['판소리'], 'recommendedCategories': ['음악']}

class RecommendationProvider:
    def __init__(self, fail=False):
        self.fail = fail

    def recommend(self, db, query, locale, limit):
        if self.fail:
            raise HTTPException(502, 'Provider unavailable')
        return {'answer': '체험 추천', 'recommendedExperienceIds': [101], 'reasons': {'101': '한지 공예'}, 'matchingKeywords': ['한지'], 'sources': []}

@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, 'internal_api_key', 'test-key')
    monkeypatch.setattr(settings, 'ai_fallback_enabled', False)
    app.dependency_overrides[deps.get_db] = lambda: HealthyDb()
    app.dependency_overrides[ai.get_culture_rag_service_factory] = lambda: lambda: ExplainProvider()
    monkeypatch.setattr(ai, 'get_experience_rag_service', lambda: RecommendationProvider())
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()

@pytest.mark.parametrize('name', ['explain', 'recommendation'])
def test_existing_success_json_remains_unchanged(client, name):
    case = SNAPSHOT[name]
    response = client.post(case['path'], json=case['request'], headers={'X-Internal-Api-Key': 'test-key'})
    assert response.status_code == case['statusCode']
    assert response.json() == case['response']


def test_existing_recommendation_failure_keeps_fallback_shape(client, monkeypatch):
    monkeypatch.setattr(ai, 'get_experience_rag_service', lambda: RecommendationProvider(fail=True))
    case = SNAPSHOT['recommendationFailure']
    response = client.post(case['path'], json=case['request'], headers={'X-Internal-Api-Key': 'test-key'})
    assert response.status_code == case['statusCode']
    assert response.json() == case['response']

@pytest.mark.parametrize('name,headers', [('missingKey', {}), ('invalidKey', {'X-Internal-Api-Key': 'wrong'})])
def test_existing_auth_error_json_remains_unchanged(client, name, headers):
    case = SNAPSHOT[name]
    response = client.post(case['path'], json=case['request'], headers=headers)
    assert response.status_code == case['statusCode']
    assert response.json() == case['response']


def test_legacy_request_range_is_not_replaced_by_agent_request(client):
    # Existing explain accepts >500 characters; existing recommendation accepts headCount=100.
    assert client.post('/api/v1/ai/explain', json={'query': '가' * 501}, headers={'X-Internal-Api-Key': 'test-key'}).status_code == 200
    assert client.post('/api/v1/ai/recommendations', json={'freeText': '한지', 'headCount': 100}, headers={'X-Internal-Api-Key': 'test-key'}).status_code == 200
