import json
from pathlib import Path

from app.schemas.ai import ExplainResponse
from app.services.ai.fallback_service import FallbackService


FALLBACK_PATH = Path("app/data/ai_fallback_responses.json")


def test_demo_fallback_file_is_frozen_and_schema_valid():
    data = json.loads(FALLBACK_PATH.read_text(encoding="utf-8"))

    assert data["fallback_mode"] == "DEMO"
    assert data["last_updated"] == "2026-06-19"
    assert set(data["responses"]) == {"판소리", "한복", "부채춤", "매듭", "탈춤"}

    for response in data["responses"].values():
        ExplainResponse.model_validate(response)


def test_demo_fallback_keyword_matching():
    service = FallbackService(str(FALLBACK_PATH))

    response = service.get_fallback_response("판소리 배우기")

    assert response is not None
    assert response["sources"][0]["name"] == "판소리"
    assert "음악" in response["recommendedCategories"]


def test_demo_fallback_does_not_invent_unmatched_query():
    service = FallbackService(str(FALLBACK_PATH))

    assert service.get_fallback_response("없는 fallback 키워드") is None
