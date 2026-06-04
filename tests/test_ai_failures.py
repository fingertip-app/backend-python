from collections.abc import Callable

import pytest
from fastapi import HTTPException, status
from fastapi.testclient import TestClient

from app.api.v1 import deps
from app.api.v1.routers.ai import get_culture_rag_service_factory
from app.core.config import settings
from app.main import app
from tests.conftest import HealthyDb


class StaticService:
    def __init__(self, response: dict[str, object] | None = None) -> None:
        self.response = response or {
            "answer": "정상 응답",
            "sources": [],
            "matchingKeywords": [],
            "recommendedCategories": [],
        }

    def explain(self, db, query: str, locale: str) -> dict[str, object]:
        return self.response


class RaisingService:
    def __init__(self, error: Exception) -> None:
        self.error = error

    def explain(self, db, query: str, locale: str) -> dict[str, object]:
        raise self.error


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "test-internal-key")
    monkeypatch.setattr(settings, "ai_fallback_enabled", False)
    monkeypatch.setattr(settings, "ai_fallback_data_path", "app/data/ai_fallback_responses.json")
    app.dependency_overrides[deps.get_db] = lambda: HealthyDb()
    app.dependency_overrides[get_culture_rag_service_factory] = lambda: lambda: StaticService()
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def auth_headers() -> dict[str, str]:
    return {"X-Internal-Api-Key": settings.internal_api_key}


def override_service(factory: Callable[[], object]) -> None:
    app.dependency_overrides[get_culture_rag_service_factory] = lambda: factory


def test_ai_explain_missing_internal_key(client):
    response = client.post("/api/v1/ai/explain", json={"query": "판소리"})

    assert response.status_code == 401
    assert response.json()["detail"] == "Missing X-Internal-Api-Key header"


def test_ai_explain_invalid_internal_key(client):
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "판소리"},
        headers={"X-Internal-Api-Key": "wrong"},
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Invalid X-Internal-Api-Key"


def test_ai_explain_query_empty(client):
    response = client.post(
        "/api/v1/ai/explain",
        json={"query": ""},
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_ai_explain_openai_key_not_set(client):
    def missing_openai_key():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )

    override_service(missing_openai_key)

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "판소리"},
        headers=auth_headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "OpenAI API is not configured"


def test_ai_explain_embedding_failure(client):
    override_service(
        lambda: RaisingService(
            HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            )
        )
    )

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "판소리"},
        headers=auth_headers(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Embedding provider request failed"


def test_ai_explain_generation_failure(client):
    override_service(
        lambda: RaisingService(
            HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation provider request failed",
            )
        )
    )

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "한복"},
        headers=auth_headers(),
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Generation provider request failed"


def test_ai_explain_no_search_results(client):
    override_service(
        lambda: StaticService(
            {
                "answer": "관련 문화유산 자료를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
                "sources": [],
                "matchingKeywords": [],
                "recommendedCategories": [],
            }
        )
    )

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "존재하지 않는 종목"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json()["sources"] == []
    assert "찾지 못했습니다" in response.json()["answer"]


def test_ai_explain_timeout_simulation(client):
    override_service(lambda: RaisingService(TimeoutError("read timed out")))

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "부채춤"},
        headers=auth_headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI service unavailable"


def test_ai_explain_fallback_enabled(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_fallback_enabled", True)
    override_service(lambda: RaisingService(TimeoutError("read timed out")))

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "판소리 배우기"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    data = response.json()
    assert "소리꾼" in data["answer"]
    assert data["sources"][0]["name"] == "판소리"
    assert "음악" in data["recommendedCategories"]


def test_ai_explain_fallback_enabled_without_matching_data(client, monkeypatch):
    monkeypatch.setattr(settings, "ai_fallback_enabled", True)
    override_service(
        lambda: RaisingService(
            HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation provider request failed",
            )
        )
    )

    response = client.post(
        "/api/v1/ai/explain",
        json={"query": "없는 fallback 키워드"},
        headers=auth_headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI service unavailable"
