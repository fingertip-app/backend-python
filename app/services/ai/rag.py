from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import HeritageItem


class CultureRagService:
    def __init__(self, client: Any) -> None:
        self.client = client

    def explain(self, db: Session, query: str, locale: str) -> dict[str, object]:
        try:
            embedding = self._embed(query)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            ) from error

        items = self._search(db, embedding)
        sources = [self._source(item) for item in items]

        if not items:
            return {
                "answer": "관련 문화유산 자료를 찾지 못했습니다. 질문을 더 구체적으로 입력해 주세요.",
                "sources": [],
                "recommendedExperienceIds": [],
            }

        context = "\n\n".join(
            f"[{item.name} / {item.source}]\n{item.description or ''}\n{item.history or ''}"
            for item in items
        )
        try:
            response = self.client.responses.create(
                model=settings.openai_generation_model,
                instructions=(
                    "You explain Korean traditional culture using only the supplied source context. "
                    "If context is insufficient, say so. Answer in the requested locale and do not invent facts."
                ),
                input=f"Locale: {locale}\nQuestion: {query}\n\nSource context:\n{context}",
            )
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Generation provider request failed",
            ) from error
        return {
            "answer": response.output_text,
            "sources": sources,
            "recommendedExperienceIds": [],
        }

    def _embed(self, query: str) -> list[float]:
        result = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=query,
            encoding_format="float",
        )
        return result.data[0].embedding

    def _search(self, db: Session, embedding: list[float]) -> list[HeritageItem]:
        statement = (
            select(HeritageItem)
            .where(HeritageItem.embedding.is_not(None))
            .order_by(HeritageItem.embedding.cosine_distance(embedding))
            .limit(settings.rag_top_k)
        )
        return list(db.scalars(statement).all())

    @staticmethod
    def _source(item: HeritageItem) -> dict[str, object]:
        return {
            "id": item.id,
            "name": item.name,
            "source": item.source,
            "category": item.category,
        }


def get_culture_rag_service() -> CultureRagService:
    if not settings.openai_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API is not configured",
        )
    return CultureRagService(OpenAI(api_key=settings.openai_api_key))
