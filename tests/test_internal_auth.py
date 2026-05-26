import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


def test_health_without_auth(client):
    """Health endpoint should not require authentication."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


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
    assert "recommendedExperienceIds" in data
