import pytest
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.core.config import settings
from app.main import app
from app.services.ai.rag import get_culture_rag_service
from tests.conftest import HealthyDb


class StubCultureRagService:
    def explain(self, db, query: str, locale: str) -> dict[str, object]:
        return {
            "answer": f"{query}:{locale}",
            "sources": [],
            "matchingKeywords": [],
            "recommendedCategories": [],
        }


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture(autouse=True)
def configured_internal_api_key(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "test-internal-key")
    app.dependency_overrides[get_culture_rag_service] = lambda: StubCultureRagService()
    yield
    app.dependency_overrides.clear()


def test_health_without_auth(client):
    """Health endpoint should not require authentication."""
    def override_db():
        yield HealthyDb()

    app.dependency_overrides[deps.get_db] = override_db
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "db": "ok"}


def test_ai_explain_missing_header(client):
    """AI endpoint without header should return 401."""
    response = client.post("/api/v1/ai/explain", json={"query": "test"})
    assert response.status_code == 401
    assert "Missing X-Internal-Api-Key header" in response.json()["detail"]


def test_ai_explain_invalid_key(client):
    """AI endpoint with invalid key should return 403."""
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "test"},
        headers={"X-Internal-Api-Key": "invalid-key"},
    )
    assert response.status_code == 403
    assert "Invalid X-Internal-Api-Key" in response.json()["detail"]


def test_ai_explain_valid_key(client):
    """AI endpoint with valid key should succeed."""
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "test", "locale": "ko"},
        headers={"X-Internal-Api-Key": settings.internal_api_key},
    )
    assert response.status_code == 200
    data = response.json()
    assert "answer" in data
    assert "sources" in data
    assert "matchingKeywords" in data
    assert "recommendedCategories" in data


def test_ai_explain_rejects_unconfigured_internal_key(client, monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "")
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "test"},
        headers={"X-Internal-Api-Key": ""},
    )
    assert response.status_code == 503
    assert "not configured" in response.json()["detail"]
