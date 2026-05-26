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

    def create(self, **kwargs):
        self.call = kwargs
        return SimpleNamespace(output_text="매듭은 실을 엮어 만드는 전통 공예입니다.")


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
    item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
        description="전통 매듭 기법",
        history="오랜 생활 장식 문화",
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
