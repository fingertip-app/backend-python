import logging
import re
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import VectorDocument
from app.schemas.ai import validate_explain_response
from app.services.ai.privacy import mask_personal_data


logger = logging.getLogger(__name__)

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
                "If context is insufficient, say so. Answer in the requested locale and do not invent facts."
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
        candidates = [
            (document, 1 - float(distance_value))
            for document, distance_value in db.execute(statement).all()
        ]
        ranked = self._rank_with_lexical_boost(candidates, query)
        return self._limit_context_documents(ranked)

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
        candidate: tuple[VectorDocument, float, int],
        max_lexical_score: int,
    ) -> float:
        _, vector_score, lexical_score = candidate
        normalized_lexical_score = lexical_score / max_lexical_score if max_lexical_score else 0
        return (
            settings.rag_vector_rank_weight * vector_score
            + settings.rag_lexical_rank_weight * normalized_lexical_score
        )

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
        for suffix in KOREAN_PARTICLE_SUFFIXES:
            if token.endswith(suffix) and len(token) > len(suffix) + 1:
                return token[: -len(suffix)]
        return token

    @staticmethod
    def _lexical_score(document: VectorDocument, tokens: list[str]) -> int:
        title = (document.title or document.heritage_item.name or "").lower()
        category = (document.category or document.heritage_item.category or "").lower()
        source = (document.source or document.heritage_item.source or "").lower()
        content = (document.content or "").lower()

        score = 0
        for token in tokens:
            if token in title:
                score += 6
            if token in category:
                score += 4
            if token in content:
                score += 2
            if token in source:
                score += 1
        return score

    @staticmethod
    def _limit_context_documents(documents: list[VectorDocument]) -> list[VectorDocument]:
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
        return list(
            dict.fromkeys(
                (document.title or document.heritage_item.name)
                for document in documents
                if document.title or document.heritage_item.name
            )
        )

    @staticmethod
    def _categories(documents: list[VectorDocument]) -> list[str]:
        return list(
            dict.fromkeys(
                (document.category or document.heritage_item.category)
                for document in documents
                if document.category or document.heritage_item.category
            )
        )


def get_culture_rag_service() -> CultureRagService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )
    return CultureRagService(OpenAI(api_key=settings.openai_api_key))
