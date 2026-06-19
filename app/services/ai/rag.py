import logging
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

        documents = self._search(db, embedding)
        sources = [self._source(document) for document in documents]

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
            if locale != "ko":
                logger.warning(
                    "Generation failed; retrying with Korean fallback",
                    extra={"locale": locale, "fallback_locale": "ko"},
                )
                try:
                    answer = self._generate_answer(context, safe_query, "ko")
                except OpenAIError as fallback_error:
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

    def _search(self, db: Session, embedding: list[float]) -> list[VectorDocument]:
        statement = (
            select(VectorDocument)
            .where(VectorDocument.embedding.is_not(None))
            .where(
                VectorDocument.embedding.cosine_distance(embedding)
                <= 1 - settings.rag_similarity_threshold
            )
            .order_by(VectorDocument.embedding.cosine_distance(embedding))
            .limit(settings.rag_top_k)
        )
        return list(db.scalars(statement).all())

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
