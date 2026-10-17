from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from openai import APIConnectionError

from app.core.config import settings
from app.etl.embed_heritage import build_embedding_text
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

    def execute(self, statement):
        self.statement = statement
        return SimpleNamespace(all=lambda: [(item, 0.2) for item in self.items])


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
    # matchingKeywords are app experience tag candidates mapped from heritage terms.
    assert sorted(result["matchingKeywords"]) == sorted(["전통매듭", "체험형", "소품만들기"])
    assert sorted(result["recommendedCategories"]) == sorted(["체험형", "소품만들기"])
    assert client.embeddings.call["model"] == "embedding-model"
    assert "매듭이 뭐예요?" in client.responses.call["input"]
    assert client.responses.call["model"] == "generation-model"


def test_build_embedding_text_includes_search_metadata():
    heritage_item = SimpleNamespace(
        name="자수장",
        source="국가유산포털",
        category="공예",
        history="조선시대 궁중 수방에서 발달했다.",
    )

    text = build_embedding_text(heritage_item, "비단에 수를 놓는 전통 기술")

    assert "이름: 자수장" in text
    assert "분류: 공예" in text
    assert "출처: 국가유산포털" in text
    assert "역사: 조선시대 궁중 수방에서 발달했다." in text
    assert "본문: 비단에 수를 놓는 전통 기술" in text


def test_explain_deduplicates_sources_for_multiple_chunks():
    client = FakeClient()
    heritage_item = SimpleNamespace(
        id=7,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    first_chunk = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="전통 매듭 기법",
        heritage_item=heritage_item,
    )
    second_chunk = SimpleNamespace(
        title="매듭장",
        source="국가유산포털",
        category="공예",
        content="생활 장식 문화",
        heritage_item=heritage_item,
    )
    service = CultureRagService(client)

    result = service.explain(FakeDb([first_chunk, second_chunk]), "매듭", "ko")

    assert result["sources"] == [
        {"id": 7, "name": "매듭장", "source": "국가유산포털", "category": "공예"}
    ]
    assert "전통 매듭 기법" in client.responses.call["input"]
    assert "생활 장식 문화" in client.responses.call["input"]


def test_search_lexical_boost_promotes_keyword_matches():
    client = FakeClient()
    weak_vector_match = SimpleNamespace(
        id=1,
        name="탈춤",
        source="국가유산포털",
        category="연희",
    )
    exact_keyword_match = SimpleNamespace(
        id=2,
        name="자수장",
        source="국가유산포털",
        category="공예",
    )
    candidates = [
        SimpleNamespace(
            title="탈춤",
            source="국가유산포털",
            category="연희",
            content="조선 후기 민속 연희",
            heritage_item=weak_vector_match,
        ),
        SimpleNamespace(
            title="자수장",
            source="국가유산포털",
            category="공예",
            content="조선시대 궁중 자수와 수방 문화",
            heritage_item=exact_keyword_match,
        ),
    ]
    service = CultureRagService(client)

    ranked = service._rank_with_lexical_boost(
        [(candidates[0], 0.23), (candidates[1], 0.22)],
        "조선시대 궁중 자수에 대해 알려주세요",
    )

    assert ranked[0].title == "자수장"


def test_search_combined_rank_keeps_strong_vector_match_when_lexical_scores_tie():
    client = FakeClient()
    strong_vector_match = SimpleNamespace(
        id=1,
        name="매듭장",
        source="국가유산포털",
        category="공예",
    )
    weak_vector_match = SimpleNamespace(
        id=2,
        name="자수장",
        source="국가유산포털",
        category="공예",
    )
    candidates = [
        SimpleNamespace(
            title="매듭장",
            source="국가유산포털",
            category="공예",
            content="전통 공예 기술",
            heritage_item=strong_vector_match,
        ),
        SimpleNamespace(
            title="자수장",
            source="국가유산포털",
            category="공예",
            content="전통 공예 기술",
            heritage_item=weak_vector_match,
        ),
    ]
    service = CultureRagService(client)

    ranked = service._rank_with_lexical_boost(
        [(candidates[0], 0.8), (candidates[1], 0.3)],
        "전통 공예",
    )

    assert ranked[0].title == "매듭장"


def test_rank_weights_are_normalized(monkeypatch):
    monkeypatch.setattr(settings, "rag_vector_rank_weight", 7)
    monkeypatch.setattr(settings, "rag_lexical_rank_weight", 3)

    assert CultureRagService._rank_weights() == (0.7, 0.3)


def test_rank_weights_fall_back_when_configured_weights_are_not_positive(monkeypatch):
    monkeypatch.setattr(settings, "rag_vector_rank_weight", 0)
    monkeypatch.setattr(settings, "rag_lexical_rank_weight", -1)

    assert CultureRagService._rank_weights() == (0.7, 0.3)


def test_limit_context_documents_caps_distinct_items(monkeypatch):
    monkeypatch.setattr(settings, "rag_top_k", 2)
    monkeypatch.setattr(settings, "rag_context_max_chunks", 10)
    first_item = SimpleNamespace(id=1)
    second_item = SimpleNamespace(id=2)
    third_item = SimpleNamespace(id=3)
    documents = [
        SimpleNamespace(heritage_item=first_item),
        SimpleNamespace(heritage_item=first_item),
        SimpleNamespace(heritage_item=second_item),
        SimpleNamespace(heritage_item=third_item),
    ]

    limited = CultureRagService._limit_context_documents(documents)

    assert limited == documents[:3]
    assert third_item.id not in {document.heritage_item.id for document in limited}


def test_limit_context_documents_caps_total_chunks(monkeypatch):
    monkeypatch.setattr(settings, "rag_top_k", 10)
    monkeypatch.setattr(settings, "rag_context_max_chunks", 2)
    first_item = SimpleNamespace(id=1)
    second_item = SimpleNamespace(id=2)
    documents = [
        SimpleNamespace(heritage_item=first_item),
        SimpleNamespace(heritage_item=first_item),
        SimpleNamespace(heritage_item=second_item),
    ]

    limited = CultureRagService._limit_context_documents(documents)

    assert limited == documents[:2]


def test_query_tokens_do_not_strip_valid_korean_word_edges():
    service = CultureRagService(FakeClient())

    tokens = service._query_tokens("도자기 만들기와 가야금에 대해 알려주세요")

    assert "도자기" in tokens
    assert "가야금" in tokens
    assert "자기" not in tokens
    assert "야금" not in tokens


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


def test_get_idf_falls_back_to_one_when_cache_not_initialized(monkeypatch):
    monkeypatch.setattr(CultureRagService, "_idf_cache", None)

    assert CultureRagService._get_idf("도자기") == 1.0


def test_lexical_score_weights_rare_tokens_more_than_common_tokens(monkeypatch):
    monkeypatch.setattr(
        CultureRagService,
        "_idf_cache",
        {"도자기": 5.0, "전통": 1.5},
    )
    heritage_item = SimpleNamespace(
        id=1,
        name="옹기장",
        source="국가유산포털",
        category="공예",
    )
    rare_in_content = SimpleNamespace(
        title="옹기장",
        source="국가유산포털",
        category="공예",
        content="도자기를 만드는 전통 기술",
        heritage_item=heritage_item,
    )

    score = CultureRagService._lexical_score(rare_in_content, ["도자기", "전통"])

    expected = 2 * (5.0 ** 2) + 2 * (1.5 ** 2)
    assert score == pytest.approx(expected)


def test_cap_chunks_per_item_limits_candidates_per_heritage_item(monkeypatch):
    monkeypatch.setattr(settings, "rag_max_chunks_per_item", 3)
    heritage_item = SimpleNamespace(id=1)
    other_item = SimpleNamespace(id=2)
    candidates = [
        (SimpleNamespace(heritage_item=heritage_item), 0.9),
        (SimpleNamespace(heritage_item=heritage_item), 0.8),
        (SimpleNamespace(heritage_item=heritage_item), 0.7),
        (SimpleNamespace(heritage_item=heritage_item), 0.6),
        (SimpleNamespace(heritage_item=other_item), 0.5),
    ]

    capped = CultureRagService._cap_chunks_per_item(
        candidates, settings.rag_max_chunks_per_item
    )

    heritage_item_count = sum(1 for doc, _ in capped if doc.heritage_item.id == 1)
    assert heritage_item_count == 3
    assert len(capped) == 4
    assert capped[0][1] == 0.9
    assert capped[2][1] == 0.7
