from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openai import APIConnectionError

from app.core.config import settings
from app.services.ai.rag import CultureRagService, get_culture_rag_service


class FakeEmbeddings:
    def __init__(self) -> None:
        self.call = None

    def create(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(data=[SimpleNamespace(embedding=[0.1, 0.2])])


class FakeResponses:
    def __init__(self) -> None:
        self.call = None
        self.calls = []
        self.output_text = "매듭은 실을 엮어 만드는 전통 공예입니다."

    def create(self, **kwargs):
        self.call = kwargs
        self.calls.append(kwargs)
        return SimpleNamespace(output_text=self.output_text)


class FailingThenSuccessfulResponses:
    def __init__(self) -> None:
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if len(self.calls) == 1:
            raise APIConnectionError(request=None)
        return SimpleNamespace(output_text="한국어 fallback 응답입니다.")


class FakeClient:
    def __init__(self) -> None:
        self.embeddings = FakeEmbeddings()
        self.responses = FakeResponses()


class FailingEmbeddings:
    def create(self, **kwargs):
        raise APIConnectionError(request=None)


class FakeDb:
    def __init__(self, items) -> None:
        self.items = items
        self.statement = None

    def scalars(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: self.items)


def test_explain_retrieves_sources_and_generates_answer(monkeypatch):
    monkeypatch.setattr(settings, "openai_embedding_model", "embedding-model")
    monkeypatch.setattr(settings, "openai_generation_model", "generation-model")
    client = FakeClient()
    heritage_item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    item = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="전통 매듭 기법\n오랜 생활 장식 문화",
        heritage_item=heritage_item,
    )
    service = CultureRagService(client)

    result = service.explain(FakeDb([item]), "매듭이 뭐예요?", "ko")

    assert result["answer"] == "매듭은 실을 엮어 만드는 전통 공예입니다."
    assert result["sources"] == [
        {"id": 7, "name": "매듭장", "source": "국가유산포털", "category": "공예"}
    ]
    assert result["matchingKeywords"] == ["매듭장"]
    assert result["recommendedCategories"] == ["공예"]
    assert client.embeddings.call["model"] == "embedding-model"
    assert "매듭이 뭐예요?" in client.responses.call["input"]
    assert client.responses.call["model"] == "generation-model"


def test_explain_uses_requested_locale_and_masks_personal_data():
    client = FakeClient()
    heritage_item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    item = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="전통 매듭 기법\n오랜 생활 장식 문화",
        heritage_item=heritage_item,
    )
    service = CultureRagService(client)

    service.explain(FakeDb([item]), "john@example.com 010-1234-5678에게 영어로 설명", "en")

    assert client.embeddings.call["input"] == "[email] [phone]에게 영어로 설명"
    assert "Locale: en" in client.responses.call["input"]
    assert "john@example.com" not in client.responses.call["input"]
    assert "010-1234-5678" not in client.responses.call["input"]


def test_explain_does_not_generate_answer_without_sources():
    client = FakeClient()
    service = CultureRagService(client)

    result = service.explain(FakeDb([]), "없는 질문", "ko")

    assert result["sources"] == []
    assert result["matchingKeywords"] == []
    assert result["recommendedCategories"] == []
    assert client.responses.call is None


def test_rag_service_requires_openai_api_key(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "")

    with pytest.raises(HTTPException) as error:
        get_culture_rag_service()

    assert error.value.status_code == 503


def test_explain_maps_embedding_provider_failure_to_bad_gateway():
    client = FakeClient()
    client.embeddings = FailingEmbeddings()
    service = CultureRagService(client)

    with pytest.raises(HTTPException) as error:
        service.explain(FakeDb([]), "매듭", "ko")

    assert error.value.status_code == 502


def test_explain_rejects_invalid_generation_schema():
    client = FakeClient()
    client.responses.output_text = ""
    heritage_item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    item = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="전통 매듭 기법\n오랜 생활 장식 문화",
        heritage_item=heritage_item,
    )
    service = CultureRagService(client)

    with pytest.raises(HTTPException) as error:
        service.explain(FakeDb([item]), "매듭", "ko")

    assert error.value.status_code == 502
    assert error.value.detail == "Generation response schema validation failed"


def test_explain_falls_back_to_korean_when_non_korean_generation_fails(caplog):
    client = FakeClient()
    client.responses = FailingThenSuccessfulResponses()
    heritage_item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    item = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="전통 매듭 기법",
        heritage_item=heritage_item,
    )
    service = CultureRagService(client)

    with caplog.at_level("INFO", logger="app.services.ai.rag"):
        result = service.explain(FakeDb([item]), "매듭", "en")

    assert result["answer"] == "한국어 fallback 응답입니다."
    assert "Locale: en" in client.responses.calls[0]["input"]
    assert "Locale: ko" in client.responses.calls[1]["input"]
    assert "Generation failed; retrying with fallback locale" in caplog.text
    assert "Fallback locale generation succeeded" in caplog.text
