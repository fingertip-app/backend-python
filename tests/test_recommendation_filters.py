from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.v1.deps import get_db
from app.api.v1.routers import ai
from app.core.config import settings
from app.main import app
from app.services.ai.recommendation_filters import RecommendationFilters


@pytest.mark.parametrize("values", [
    {"maxPrice": -1}, {"maxDurationMinutes": 0}, {"headCount": 0},
    {"region": "%"}, {"region": "서울|부산"}, {"heritageItemId": 0},
])
def test_invalid_constraints_are_rejected(values):
    with pytest.raises(ValidationError):
        RecommendationFilters(**values)


def test_nationwide_is_not_a_literal_address_filter():
    assert RecommendationFilters(region=" 전국 ").region is None
    assert RecommendationFilters(maxPrice=0).maxPrice == 0


def test_clear_text_constraints_are_extracted_and_form_wins():
    parsed = RecommendationFilters.resolve("경기도에서 3만 원 이하 도자기 체험")
    assert parsed.region == "경기"
    assert parsed.maxPrice == 30000
    explicit = RecommendationFilters.resolve("서울에서 3만 원 이하", region="경남", maxPrice=0)
    assert explicit.region == "경남"
    assert explicit.maxPrice == 0


@pytest.mark.parametrize("query", ["총 3만 원 이하", "전체 30,000원 이하", "3.5만 원 이하", "0원 미만", "-1만원 이하"])
def test_ambiguous_prices_are_not_inferred(query):
    assert RecommendationFilters.resolve(query).maxPrice is None


def test_multiple_regions_and_negative_region_are_not_guessed():
    assert RecommendationFilters.resolve("서울에서 또는 부산에서").region is None
    assert RecommendationFilters.resolve("서울말고 다른 곳").region is None


@pytest.mark.parametrize("query,message", [
    ("서울에서 또는 부산에서 도자 체험", "지역 조건 확인 필요"),
    ("0원 미만 도자 체험", "예산 조건 확인 필요"),
    ("총 3만 원 이하 가족 체험", "예산 조건 확인 필요"),
])
def test_ambiguous_conditions_do_not_call_recommender(monkeypatch, query, message):
    monkeypatch.setattr(settings, "internal_api_key", "test-key")

    def unexpected_recommend(*args, **kwargs):
        pytest.fail("Clarification must not silently search without constraints")

    monkeypatch.setattr(ai, "get_experience_rag_service", lambda: SimpleNamespace(recommend=unexpected_recommend))
    app.dependency_overrides[get_db] = lambda: object()
    try:
        response = TestClient(app).post("/api/v1/ai/recommendations", json={"freeText": query},
                                        headers={"X-Internal-Api-Key": "test-key"})
        assert response.status_code == 200
        assert response.json()["message"] == message
        assert response.json()["recommendedExperienceIds"] == []
        assert response.json()["fallback"] is False
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_api_passes_constraints_to_search_without_changing_existing_contract(monkeypatch):
    monkeypatch.setattr(settings, "internal_api_key", "test-key")
    captured = {}

    def recommend(db, query, locale, limit, filters):
        captured["filters"] = filters
        return {"answer": "조건에 맞는 체험 없음", "recommendedExperienceIds": [],
                "reasons": {}, "sources": []}

    monkeypatch.setattr(ai, "get_experience_rag_service", lambda: SimpleNamespace(recommend=recommend))
    app.dependency_overrides[get_db] = lambda: object()
    try:
        result = TestClient(app).post("/api/v1/ai/recommendations", headers={
            "X-Internal-Api-Key": "test-key",
        }, json={"freeText": "상감 배우기", "region": "경기 이천시", "maxPrice": 30000,
                 "maxDurationMinutes": 90, "headCount": 3, "technique": "상감"})
        assert result.status_code == 200
        assert result.json()["recommendedExperienceIds"] == []
        assert result.json()["fallback"] is False
        assert captured["filters"].model_dump(exclude_none=True) == {
            "region": "경기 이천시", "maxPrice": 30000,
            "maxDurationMinutes": 90, "headCount": 3, "technique": "상감",
        }
    finally:
        app.dependency_overrides.pop(get_db, None)
