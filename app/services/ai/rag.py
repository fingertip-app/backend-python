import logging
import math
import re
from collections import Counter
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HeritageItem, VectorDocument
from app.schemas.ai import validate_explain_response
from app.services.ai.privacy import mask_personal_data


logger = logging.getLogger(__name__)

# Lightweight tokenization: matches Korean syllables (가-힣), ASCII alphanumeric.
# Intentionally excludes Hanja (陶瓷器), special punctuation (·, -, etc) for simplicity.
# Example: "청자·백자" → ["청자", "백자"], "陶瓷器" → []
TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")
QUERY_STOPWORDS = {
    "대해",
    "대해서",
    "알려줘",
    "알려주세요",
    "설명",
    "설명해줘",
    "설명해주세요",
    "무엇",
    "뭐예요",
    "뭔가요",
}
KOREAN_PARTICLE_SUFFIXES = (
    "으로",
    "에서",
    "에게",
    "부터",
    "까지",
    "보다",
    "처럼",
    "은",
    "는",
    "이",
    "가",
    "을",
    "를",
    "에",
    "의",
    "와",
    "과",
    "도",
    "만",
    "로",
)


class CultureRagService:
    # 토큰별 IDF(Inverse Document Frequency) 캐시.
    # 앱 시작 시 init_idf_cache()로 1회 채워짐. None이면 _get_idf가 1.0(가중치 없음)으로 폴백해
    # 기존 동작(가중치 미적용)과 동일하게 동작한다 — 캐시 초기화 누락/실패가 서비스 장애로 번지지 않도록 함.
    _idf_cache: dict[str, float] | None = None

    def __init__(self, client: Any) -> None:
        self.client = client

    def explain(self, db: Session, query: str, locale: str) -> dict[str, object]:
        safe_query = mask_personal_data(query)
        try:
            embedding = self._embed(safe_query)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            ) from error

        documents = self._search(db, embedding, safe_query)
        # Multiple matched chunks can point to the same heritage item.
        seen_ids = set()
        sources = []
        for document in documents:
            item_id = document.heritage_item.id
            if item_id not in seen_ids:
                seen_ids.add(item_id)
                sources.append(self._source(document))

        if not documents:
            return validate_explain_response({
                "answer": "관련 문화유산 자료를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
                "sources": [],
                "matchingKeywords": [],
                "recommendedCategories": [],
            })

        context = "\n\n".join(
            f"[{document.title or document.heritage_item.name} / {document.source or document.heritage_item.source}]\n"
            f"{document.content}"
            for document in documents
        )
        try:
            answer = self._generate_answer(context, safe_query, locale)
        except OpenAIError as error:
            if locale != settings.rag_locale_fallback:
                logger.warning(
                    "Generation failed; retrying with fallback locale",
                    extra={"original_locale": locale, "fallback_locale": settings.rag_locale_fallback},
                )
                try:
                    answer = self._generate_answer(context, safe_query, settings.rag_locale_fallback)
                    logger.info(
                        "Fallback locale generation succeeded",
                        extra={"original_locale": locale, "fallback_locale": settings.rag_locale_fallback},
                    )
                except OpenAIError as fallback_error:
                    logger.error(
                        "Fallback locale generation failed",
                        extra={"original_locale": locale, "fallback_locale": settings.rag_locale_fallback},
                    )
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="Generation provider request failed",
                    ) from fallback_error
            else:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Generation provider request failed",
                ) from error

        try:
            return validate_explain_response({
                "answer": answer,
                "sources": sources,
                "matchingKeywords": self._matching_keywords(documents),
                "recommendedCategories": self._categories(documents),
            })
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation response schema validation failed",
            ) from error

    def _generate_answer(self, context: str, query: str, locale: str) -> str:
        response = self.client.responses.create(
            model=settings.openai_generation_model,
            instructions=(
                "You explain Korean traditional culture using only the supplied source context. "
                "If context is insufficient, say so. Answer in the requested locale and do not invent facts. "
                "When recommending experiences, focus on these app categories: "
                "전통섬유, 전통모자, 전통의복, 전통매듭, 전통음악, 전통공연, 전통종이, 백자, 도자기, "
                "궁중자수, 바느질, 발효, 막걸리, 물레체험, 채색체험, 소품만들기, 체험형, 하회탈, "
                "국가무형유산, 조선시대, 판소리, 장단, 닥나무, 노리개, 배색, 시음체험, 핸드빌딩"
            ),
            input=f"Locale: {locale}\nQuestion: {query}\n\nSource context:\n{context}",
        )
        return response.output_text or ""

    def _embed(self, query: str) -> list[float]:
        result = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=query,
            encoding_format="float",
        )
        return result.data[0].embedding

    def _search(self, db: Session, embedding: list[float], query: str) -> list[VectorDocument]:
        max_distance = 1 - settings.rag_similarity_threshold
        distance = VectorDocument.embedding.cosine_distance(embedding).label("distance")
        statement = (
            select(VectorDocument, distance)
            .where(VectorDocument.embedding.is_not(None))
            .where(distance <= max_distance)
            .order_by(distance)
            .limit(settings.rag_candidate_k)
        )
        raw_results = db.execute(statement).all()
        candidates = []
        for row in raw_results:
            try:
                document, distance_value = row
                candidates.append((document, 1 - float(distance_value)))
            except (ValueError, TypeError) as error:
                logger.error(
                    "Failed to unpack vector search result row",
                    extra={"error": str(error), "row": str(row)[:100]}
                )
                continue
        candidates = self._cap_chunks_per_item(candidates, settings.rag_max_chunks_per_item)
        ranked = self._rank_with_lexical_boost(candidates, query)
        return self._limit_context_documents(ranked)

    @staticmethod
    def _cap_chunks_per_item(
        candidates: list[tuple[VectorDocument, float]],
        max_per_item: int,
    ) -> list[tuple[VectorDocument, float]]:
        """
        동일 heritage_item이 candidate 슬롯을 과점하지 못하도록 item당 청크 수를 제한한다.

        텍스트가 길어 청크가 많이 생긴 항목(예: 14개)이 candidate_k 슬롯을 독점하면,
        텍스트가 짧아 청크가 적은 항목(예: 자수장 2개)이 슬롯 부족으로 밀려나는
        구조적 불균형이 생긴다. candidates는 이미 벡터 거리순으로 정렬되어 들어오므로,
        item별로 더 가까운(앞에 나온) 청크가 우선적으로 살아남는다.
        """
        item_counts: dict[int, int] = {}
        capped = []
        for document, score in candidates:
            item_id = document.heritage_item.id
            count = item_counts.get(item_id, 0)
            if count >= max_per_item:
                continue
            item_counts[item_id] = count + 1
            capped.append((document, score))
        return capped

    @classmethod
    def _rank_with_lexical_boost(
        cls,
        candidates: list[tuple[VectorDocument, float]],
        query: str,
    ) -> list[VectorDocument]:
        tokens = cls._query_tokens(query)
        if not tokens:
            return [document for document, _ in candidates]

        scored_candidates = [
            (document, vector_score, cls._lexical_score(document, tokens))
            for document, vector_score in candidates
        ]
        max_lexical_score = max(
            (lexical_score for _, _, lexical_score in scored_candidates),
            default=0,
        )

        ranked_candidates = sorted(
            scored_candidates,
            key=lambda candidate: cls._combined_rank_score(candidate, max_lexical_score),
            reverse=True,
        )
        return [document for document, _, _ in ranked_candidates]

    @staticmethod
    def _combined_rank_score(
        candidate: tuple[VectorDocument, float, float],
        max_lexical_score: float,
    ) -> float:
        _, vector_score, lexical_score = candidate
        normalized_lexical_score = lexical_score / max_lexical_score if max_lexical_score else 0
        vector_weight, lexical_weight = CultureRagService._rank_weights()
        return (
            vector_weight * vector_score
            + lexical_weight * normalized_lexical_score
        )

    @staticmethod
    def _rank_weights() -> tuple[float, float]:
        vector_weight = max(settings.rag_vector_rank_weight, 0)
        lexical_weight = max(settings.rag_lexical_rank_weight, 0)
        total = vector_weight + lexical_weight
        if total <= 0:
            logger.warning(
                "Invalid rank weight configuration, using fallback weights",
                extra={
                    "vector_weight": settings.rag_vector_rank_weight,
                    "lexical_weight": settings.rag_lexical_rank_weight,
                    "fallback": "(0.7, 0.3)"
                }
            )
            return 0.7, 0.3
        return vector_weight / total, lexical_weight / total

    @classmethod
    def _query_tokens(cls, query: str) -> list[str]:
        tokens = []
        for raw_token in TOKEN_RE.findall(query.lower()):
            token = cls._strip_particle_suffix(raw_token)
            if len(token) < 2 or token in QUERY_STOPWORDS:
                continue
            tokens.append(token)
        return list(dict.fromkeys(tokens))

    @staticmethod
    def _strip_particle_suffix(token: str) -> str:
        """
        Strip Korean particles from token if the remaining stem would be >= 2 chars.

        Boundary condition: len(token) > len(suffix) + 1 ensures minimum 2-char stem.
        Examples:
            - "도자기에" (4 chars) → "도자기" (3 chars stem, ✓)
            - "나는" (2 chars) → "나는" (1 char stem would remain, ✗ preserved)
            - "매듭으로" (4 chars) → "매듭" (2 chars stem, ✓)
        """
        for suffix in KOREAN_PARTICLE_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                return token[: -len(suffix)]
        return token

    @classmethod
    def init_idf_cache(cls, db: Session) -> None:
        """
        앱 시작 시(lifespan) 1회 호출해 IDF 캐시를 초기화한다.

        실패해도 서비스 자체는 동작해야 하므로 예외를 흡수하고 캐시를 None으로 둔다.
        캐시가 None이면 _get_idf가 1.0을 반환해 기존 동작(가중치 미적용)과 동일하게 동작한다.
        """
        try:
            cls._idf_cache = cls._compute_idf(db)
            logger.info(
                "RAG IDF cache initialized",
                extra={"token_count": len(cls._idf_cache)},
            )
        except Exception as error:
            logger.error(
                "Failed to initialize RAG IDF cache; falling back to unweighted lexical score",
                extra={"error": str(error)},
            )
            cls._idf_cache = None

    @classmethod
    def _compute_idf(cls, db: Session) -> dict[str, float]:
        """
        heritage_items 전체를 스캔해 토큰별 IDF를 계산한다.

        공식: idf(token) = log(전체 문서 수 / 그 토큰을 포함한 문서 수) + 1
        +1 smoothing: 모든 문서에 등장하는 토큰(idf=log(1)=0)도 최소 가중치 1을 갖게 해,
        기존 점수 체계(가중치 미적용 시 곱 1)와 자연스럽게 연결되도록 함.

        문서 단위는 heritage_item(80건) 기준 — vector_documents(청크) 단위로 하면
        청크 수가 많은 항목(예: 14개)의 토큰이 과대 집계되어 IDF가 왜곡됨.
        """
        items = db.query(HeritageItem).all()
        total_docs = len(items)
        if total_docs == 0:
            return {}

        doc_freq: Counter[str] = Counter()
        for item in items:
            text = " ".join(
                filter(None, [item.name, item.category, item.description, item.history])
            )
            unique_tokens = set(cls._query_tokens(text))
            for token in unique_tokens:
                doc_freq[token] += 1

        return {
            token: math.log(total_docs / freq) + 1
            for token, freq in doc_freq.items()
        }

    @classmethod
    def _get_idf(cls, token: str) -> float:
        """
        토큰의 IDF 가중치를 반환한다.

        - 캐시 미초기화(None) 시: 1.0 반환 → 기존 동작과 동일 (가중치 없음)
        - 캐시에 있는 토큰: 계산된 IDF 반환
        - 캐시에 없는 토큰(80건 어디에도 안 나타난, 질의에만 있는 매우 희귀한 단어):
          캐시 내 최댓값으로 처리 (가장 희귀한 토큰과 동등하게 취급)
        """
        if not cls._idf_cache:
            return 1.0
        if token in cls._idf_cache:
            return cls._idf_cache[token]
        return max(cls._idf_cache.values(), default=1.0)

    @classmethod
    def _lexical_score(cls, document: VectorDocument, tokens: list[str]) -> float:
        title = (document.title or document.heritage_item.name or "").lower()
        category = (document.category or document.heritage_item.category or "").lower()
        source = (document.source or document.heritage_item.source or "").lower()
        content = (document.content or "").lower()

        score = 0.0
        for token in tokens:
            # IDF를 제곱해 영향력을 키운다 — 단순 곱(idf^1)로는 title 위치 가중치(6)가
            # 흔한 토큰(낮은 idf)에도 크게 작용해, "흔한 단어가 title에 있는 문서"가
            # "희귀한 단어가 content에 있는 문서"보다 부당하게 유리해지는 역전이 발생했음.
            idf_sq = cls._get_idf(token) ** 2
            if token in title:
                score += 6 * idf_sq
            if token in category:
                score += 4 * idf_sq
            if token in content:
                score += 2 * idf_sq
            if token in source:
                score += 1 * idf_sq
        return score

    @staticmethod
    def _limit_context_documents(documents: list[VectorDocument]) -> list[VectorDocument]:
        """
        Limit context to top-K distinct heritage items and max total chunks.

        Greedy algorithm: processes ranked documents sequentially, prioritizing:
        1. First `rag_top_k` distinct heritage items
        2. Total chunks limited to `rag_context_max_chunks`

        Note: Early-ranked documents may contribute multiple chunks before
        later documents are included. This favors higher-ranked items.

        Example with rag_top_k=2, rag_context_max_chunks=5:
            Input: [item1_chunk1, item1_chunk2, item1_chunk3, item2_chunk1, item3_chunk1]
            Output: [item1_chunk1, item1_chunk2, item1_chunk3, item2_chunk1]
                    (item3 excluded because top-K distinct items are already selected)
        """
        selected_item_ids = set()
        selected_documents = []

        for document in documents:
            item_id = document.heritage_item.id
            if item_id not in selected_item_ids:
                if len(selected_item_ids) >= settings.rag_top_k:
                    continue
                selected_item_ids.add(item_id)
            selected_documents.append(document)
            if len(selected_documents) >= settings.rag_context_max_chunks:
                break

        return selected_documents

    @staticmethod
    def _source(document: VectorDocument) -> dict[str, object]:
        item = document.heritage_item
        return {
            "id": item.id,
            "name": document.title or item.name,
            "source": document.source or item.source,
            "category": document.category or item.category,
        }

    @staticmethod
    def _matching_keywords(documents: list[VectorDocument]) -> list[str]:
        """Extract keywords and map to app tags"""
        heritage_keywords = list(
            dict.fromkeys(
                (document.title or document.heritage_item.name)
                for document in documents
                if document.title or document.heritage_item.name
            )
        )
        return CultureRagService._map_to_app_tags(heritage_keywords)

    @staticmethod
    def _categories(documents: list[VectorDocument]) -> list[str]:
        """Extract categories and map to app tags"""
        heritage_categories = list(
            dict.fromkeys(
                (document.category or document.heritage_item.category)
                for document in documents
                if document.category or document.heritage_item.category
            )
        )
        return CultureRagService._map_to_app_tags(heritage_categories)

    @staticmethod
    def _map_to_app_tags(heritage_terms: list[str]) -> list[str]:
        """Map heritage keywords/categories to app experience tags"""
        # App tags available in the experience database
        APP_TAGS = {
            "전통섬유", "전통모자", "전통의복", "전통매듭", "전통음악", "전통공연",
            "전통종이", "백자", "궁중자수", "바느질", "발효", "막걸리",
            "물레체험", "채색체험", "소품만들기", "체험형", "하회탈",
            "국가무형유산", "조선시대", "판소리", "장단", "닥나무",
            "노리개", "배색", "시음체험", "핸드빌딩", "여름공예", "충북",
            "도자기"
        }

        # Mapping rules: heritage term -> app tag
        MAPPING = {
            # Textiles
            "한산모시짜기": "전통섬유",
            "모시": "전통섬유",
            "삼베": "전통섬유",
            "직조": "전통섬유",

            # Hats and accessories
            "갓일": "전통모자",
            "망건": "전통모자",
            "갓": "전통모자",

            # Traditional clothing
            "한복생활": "전통의복",
            "한복": "전통의복",

            # Knots
            "매듭장": "전통매듭",
            "매듭": "전통매듭",
            "노리개": "노리개",

            # Music and performance
            "판소리": "판소리",
            "가야금산조": "전통음악",
            "가야금": "전통음악",
            "악기장": "전통음악",
            "처용무": "전통공연",
            "탈춤": "하회탈",
            "가면극": "하회탈",

            # Paper crafts
            "한지": "전통종이",
            "닥나무": "닥나무",
            "지장": "전통종이",

            # Ceramics (도자기)
            "백자": "백자",
            "청자": "백자",
            "도자기": "백자",
            "도예": "백자",
            "사기장": "백자",
            "물레": "물레체험",
            "빚기": "물레체험",
            "핸드빌딩": "핸드빌딩",
            "달항아리": "백자",

            # Embroidery
            "자수": "궁중자수",
            "바느질": "바느질",

            # Fermented foods
            "김치": "발효",
            "장 담그기": "발효",
            "막걸리": "막걸리",
            "발효": "발효",

            # Food
            "한식": "발효",
            "전통음식": "발효",

            # Traditional knowledge
            "전통기술": "국가무형유산",
            "국가무형문화재": "국가무형유산",

            # Era
            "조선": "조선시대",
            "궁중": "궁중자수",
        }

        mapped_tags = set()

        for term in heritage_terms:
            term_lower = term.lower()

            # Direct mapping
            if term in MAPPING:
                mapped_tags.add(MAPPING[term])

            # Partial match
            for key, value in MAPPING.items():
                if key in term or term in key:
                    mapped_tags.add(value)

            # Direct match with app tags
            if term in APP_TAGS:
                mapped_tags.add(term)

        # Always include generic craft tags
        mapped_tags.add("소품만들기")
        mapped_tags.add("체험형")

        return list(mapped_tags)


def get_culture_rag_service() -> CultureRagService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )
    return CultureRagService(OpenAI(api_key=settings.openai_api_key))