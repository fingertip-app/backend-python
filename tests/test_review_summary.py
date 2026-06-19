from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from app.api.v1.routers import ai
from app.core.config import settings
from app.main import app
from app.services.ai.review_summary import ReviewSummaryService


class FakeChatCompletions:
    def __init__(self, content: str) -> None:
        self.content = content
        self.call = None

    def create(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content=self.content)
                )
            ]
        )


class FakeClient:
    def __init__(self, content: str) -> None:
        self.chat = SimpleNamespace(completions=FakeChatCompletions(content))


@pytest.fixture(autouse=True)
def cleanup_overrides():
    yield
    app.dependency_overrides.clear()


def auth_headers() -> dict[str, str]:
    return {"X-Internal-Api-Key": settings.internal_api_key}


def test_review_summary_normalizes_model_response(monkeypatch):
    monkeypatch.setattr(settings, "openai_generation_model", "generation-model")
    service = ReviewSummaryService(
        FakeClient(
            '{"summary": "좋은 전통 체험", "sentimentScore": 1.2, '
            '"keywords": ["전통", "체험", "", "배움", "공예", "초과"]}'
        )
    )

    result = service.summarize("전통 공예를 배우는 시간이 아주 만족스러웠습니다.", "ko")

    assert result == {
        "summary": "좋은 전통 체험",
        "sentimentScore": 1.0,
        "keywords": ["전통", "체험", "배움", "공예", "초과"],
    }
    assert service.client.chat.completions.call["model"] == "generation-model"


def test_review_summary_masks_personal_data_before_model_call():
    service = ReviewSummaryService(
        FakeClient('{"summary": "연락처는 제외하고 요약", "sentimentScore": 0.7, "keywords": ["친절"]}')
    )

    service.summarize("담당자가 john@example.com 와 010-1234-5678로 친절히 안내했습니다.", "ko")

    user_message = service.client.chat.completions.call["messages"][1]["content"]
    assert "john@example.com" not in user_message
    assert "010-1234-5678" not in user_message
    assert "[email]" in user_message
    assert "[phone]" in user_message


def test_review_summary_english_locale_prompt():
    service = ReviewSummaryService(
        FakeClient('{"summary": "A satisfying craft class.", "sentimentScore": 0.9, "keywords": ["craft"]}')
    )

    service.summarize("The instructor was kind and the craft class was memorable.", "en")

    system_message = service.client.chat.completions.call["messages"][0]["content"]
    assert "in English" in system_message


def test_review_summary_short_review_does_not_call_model():
    service = ReviewSummaryService(FakeClient('{"summary": "should not be used"}'))

    result = service.summarize("좋아요", "ko")

    assert result == {
        "summary": "좋아요",
        "sentimentScore": 0.5,
        "keywords": [],
    }
    assert service.client.chat.completions.call is None


def test_review_summary_short_review_does_not_require_openai_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")
    service = ReviewSummaryService()

    result = service.summarize("좋아요", "ko")

    assert result == {
        "summary": "좋아요",
        "sentimentScore": 0.5,
        "keywords": [],
    }


def test_review_summary_route_returns_503_on_provider_failure(monkeypatch):
    class FailingService:
        def summarize(self, content: str, locale: str):
            raise RuntimeError("provider failed")

    monkeypatch.setattr(settings, "internal_api_key", "test-internal-key")
    monkeypatch.setattr(ai, "ReviewSummaryService", FailingService)

    response = TestClient(app).post(
        "/api/v1/ai/review-summary",
        json={"content": "정말 만족스러운 전통 체험이었습니다.", "locale": "ko"},
        headers=auth_headers(),
    )

    assert response.status_code == 503
    assert response.json()["detail"] == "AI service unavailable"


def test_review_summary_route_success(monkeypatch):
    class StaticService:
        def summarize(self, content: str, locale: str):
            return {
                "summary": "만족스러운 전통 체험",
                "sentimentScore": 0.9,
                "keywords": ["전통", "만족"],
            }

    monkeypatch.setattr(settings, "internal_api_key", "test-internal-key")
    monkeypatch.setattr(ai, "ReviewSummaryService", StaticService)

    response = TestClient(app).post(
        "/api/v1/ai/review-summary",
        json={"content": "정말 만족스러운 전통 체험이었습니다.", "locale": "ko"},
        headers=auth_headers(),
    )

    assert response.status_code == 200
    assert response.json() == {
        "summary": "만족스러운 전통 체험",
        "sentimentScore": 0.9,
        "keywords": ["전통", "만족"],
    }
