"""
Experience 기반 RAG 서비스

CultureRagService와 유사하지만, 실제 예약 가능한 체험 데이터를 벡터 검색하여 추천합니다.
"""
import logging
from typing import Any

from fastapi import HTTPException, status
from openai import OpenAI, OpenAIError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Experience
from app.services.ai.privacy import mask_personal_data

logger = logging.getLogger(__name__)


class ExperienceRagService:
    """체험 프로그램 벡터 검색 및 AI 추천 서비스"""

    def __init__(self, client: OpenAI) -> None:
        self.client = client

    def recommend(
        self,
        db: Session,
        query: str,
        locale: str = "ko",
        limit: int = 5
    ) -> dict[str, Any]:
        """
        사용자 쿼리를 기반으로 체험 프로그램 추천

        Args:
            db: DB 세션
            query: 사용자 질문/선호도 (예: "혼자서 조용히 만들기 체험 하고 싶어요")
            locale: 언어 코드
            limit: 추천할 체험 개수

        Returns:
            {
                "answer": "AI 생성 추천 설명",
                "recommendedExperiences": [...],
                "matchingKeywords": [...],
                "sources": [...]
            }
        """
        safe_query = mask_personal_data(query)

        try:
            embedding = self._embed(safe_query)
        except OpenAIError as error:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Embedding provider request failed",
            ) from error

        experiences = self._search_experiences(db, embedding, limit)

        if not experiences:
            return {
                "answer": "현재 조건에 맞는 체험을 찾지 못했습니다. 다른 키워드로 검색해보시겠어요?",
                "recommendedExperienceIds": [],
                "reasons": {},
                "matchingKeywords": [],
            }

        # AI 답변 생성
        try:
            answer = self._generate_recommendation_answer(experiences, safe_query, locale)
        except OpenAIError as error:
            logger.error(f"AI 답변 생성 실패: {error}")
            answer = "선택하신 취향을 바탕으로 가장 적합한 체험을 찾았어요."

        return {
            "answer": answer,
            "recommendedExperienceIds": [exp.id for exp in experiences],
            "reasons": {
                str(exp.id): self._extract_match_reason(exp, safe_query)
                for exp in experiences
            },
            "matchingKeywords": self._extract_keywords(experiences),
        }

    def _embed(self, text: str) -> list[float]:
        """텍스트를 OpenAI 임베딩 벡터로 변환"""
        result = self.client.embeddings.create(
            model=settings.openai_embedding_model,
            input=text,
            encoding_format="float",
        )
        return result.data[0].embedding

    def _search_experiences(
        self,
        db: Session,
        embedding: list[float],
        limit: int
    ) -> list[Experience]:
        """벡터 유사도 기반 체험 검색"""
        max_distance = 1 - settings.rag_similarity_threshold
        distance = Experience.description_embedding.cosine_distance(embedding).label("distance")

        stmt = (
            select(Experience, distance)
            .where(Experience.is_active.is_(True))
            .where(Experience.description_embedding.is_not(None))
            .where(distance <= max_distance)
            .order_by(distance)
            .limit(limit)
        )

        raw_results = db.execute(stmt).all()
        experiences = []

        for row in raw_results:
            try:
                experience, _ = row
                experiences.append(experience)
            except (ValueError, TypeError) as error:
                logger.error(
                    "Failed to unpack experience search result",
                    extra={"error": str(error), "row": str(row)[:100]}
                )
                continue

        return experiences

    def _generate_recommendation_answer(
        self,
        experiences: list[Experience],
        query: str,
        locale: str
    ) -> str:
        """추천 체험에 대한 AI 설명 생성"""
        context = "\n\n".join(
            f"[{exp.title}]\n카테고리: {exp.category}\n설명: {exp.description[:200]}"
            for exp in experiences
        )

        response = self.client.responses.create(
            model=settings.openai_generation_model,
            instructions=(
                "You are a traditional Korean culture experience recommender. "
                "Based on the user's preferences and the provided experiences, "
                "write a warm, personalized recommendation in the requested locale. "
                "Keep it concise (2-3 sentences)."
            ),
            input=f"Locale: {locale}\nUser preference: {query}\n\nRecommended experiences:\n{context}",
        )

        return response.output_text or "선택하신 취향을 바탕으로 가장 적합한 체험을 찾았어요."

    def _extract_match_reason(self, experience: Experience, query: str) -> str:
        """왜 이 체험이 추천되었는지 간단한 이유 생성"""
        # 쿼리에서 키워드 추출 (간단한 버전)
        if "혼자" in query or "solo" in query.lower():
            return "혼자서도 편하게 즐길 수 있어요"
        if "가족" in query or "family" in query.lower():
            return "가족과 함께 즐기기 좋아요"
        if "만들" in query or "craft" in query.lower():
            return "직접 만들어보는 체험이에요"
        if "조용" in query or "quiet" in query.lower():
            return "조용하고 차분한 분위기예요"

        # 기본값: 카테고리 기반
        return f"{experience.category} 체험이에요"

    def _extract_keywords(self, experiences: list[Experience]) -> list[str]:
        """추천된 체험들에서 공통 키워드 추출"""
        keywords = set()
        for exp in experiences:
            keywords.add(exp.category)
            if exp.difficulty:
                keywords.add(exp.difficulty)

        return list(keywords)[:5]


def get_experience_rag_service() -> ExperienceRagService:
    """의존성 주입용 팩토리 함수"""
    client = OpenAI(api_key=settings.openai_api_key)
    return ExperienceRagService(client)
