import logging
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.core.config import settings
from app.core.security import verify_internal_api_key
from app.schemas.ai import ExplainResponse
from app.services.ai.experience_rag import ExperienceRagService, get_experience_rag_service
from app.services.ai.fallback_service import FallbackService
from app.services.ai.rag import CultureRagService, get_culture_rag_service
from app.services.ai.review_summary import ReviewSummaryService

router = APIRouter(dependencies=[Depends(verify_internal_api_key)])
logger = logging.getLogger(__name__)

# 로그에 기록할 최대 쿼리 길이
MAX_QUERY_LOG_LENGTH = 200
# API가 허용하는 최대 쿼리 길이
MAX_QUERY_LENGTH = 5000


def _get_safe_query_preview(query: str) -> str:
    """
    쿼리를 안전하게 로깅하기 위해 truncate 처리.
    민감 정보 노출 방지 및 로그 볼륨 제어.
    """
    if len(query) > MAX_QUERY_LOG_LENGTH:
        return f"{query[:MAX_QUERY_LOG_LENGTH]}...[truncated, total: {len(query)} chars]"
    return query


class ExplainRequest(BaseModel):
    query: str = Field(min_length=1, max_length=MAX_QUERY_LENGTH, description="사용자 질문 (최소 1자, 최대 5000자)")
    locale: str = Field(default="ko", description="언어 코드")


class ReviewSummaryRequest(BaseModel):
    content: str = Field(min_length=1)
    locale: str = "ko"


class ReviewSummaryResponse(BaseModel):
    summary: str
    sentimentScore: float
    keywords: list[str]


def get_culture_rag_service_factory() -> Callable[[], CultureRagService]:
    return get_culture_rag_service


@router.post("/explain", response_model=ExplainResponse)
def explain_culture(
    payload: ExplainRequest,
    request: Request,
    db: Session = Depends(get_db),
    service_factory: Callable[[], CultureRagService] = Depends(get_culture_rag_service_factory),
) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    query_preview = _get_safe_query_preview(payload.query)
    logger.info(
        "AI explain request started",
        extra={
            "request_id": request_id,
            "query_preview": query_preview,
            "query_length": len(payload.query),
            "locale": payload.locale,
        },
    )
    try:
        service = service_factory()
        response = service.explain(db, payload.query, payload.locale)
        logger.info(
            "AI explain request completed",
            extra={"request_id": request_id, "source_count": len(response.get("sources", []))},
        )
        return response
    except HTTPException as error:
        if not _should_try_fallback(error):
            logger.warning(
                "AI explain request failed",
                extra={"request_id": request_id, "status_code": error.status_code},
            )
            raise

        fallback = FallbackService().get_fallback_response(payload.query)
        if fallback:
            logger.warning(
                "AI fallback response served",
                extra={"request_id": request_id, "status_code": error.status_code},
            )
            return fallback

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable",
        ) from error
    except Exception as error:
        logger.exception("AI explanation failed unexpectedly", extra={"request_id": request_id})
        if settings.ai_fallback_enabled:
            fallback = FallbackService().get_fallback_response(payload.query)
            if fallback:
                logger.warning("AI fallback response served", extra={"request_id": request_id})
                return fallback
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable",
        ) from error


def _should_try_fallback(error: HTTPException) -> bool:
    return settings.ai_fallback_enabled and error.status_code in {
        status.HTTP_502_BAD_GATEWAY,
        status.HTTP_503_SERVICE_UNAVAILABLE,
    }


@router.post("/review-summary", response_model=ReviewSummaryResponse)
def review_summary(payload: ReviewSummaryRequest, request: Request) -> dict[str, Any]:
    request_id = getattr(request.state, "request_id", None)
    logger.info("Review summary request started", extra={"request_id": request_id})
    try:
        service = ReviewSummaryService()
        response = service.summarize(payload.content, payload.locale)
        logger.info("Review summary request completed", extra={"request_id": request_id})
        return response
    except Exception as error:
        logger.exception("Review summary failed unexpectedly", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable",
        ) from error


class RecommendationRequest(BaseModel):
    freeText: str = Field(min_length=1, max_length=500)
    companionType: str = Field(default="OTHER")
    headCount: int = Field(default=2, ge=1, le=100)
    interests: list[str] = Field(default_factory=list, max_length=10)
    region: str | None = Field(default=None)
    timePreference: str = Field(default="ANYTIME")
    conversationHistory: list[dict[str, str]] = Field(default_factory=list, max_length=20)
    locale: str = Field(default="ko")


@router.post("/recommendations")
def get_recommendations(
    payload: RecommendationRequest,
    request: Request,
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """체험 프로그램 AI 추천 엔드포인트"""
    request_id = getattr(request.state, "request_id", None)
    logger.info(
        "AI recommendation request started",
        extra={
            "request_id": request_id,
            "companion_type": payload.companionType,
            "interests": payload.interests,
        },
    )

    try:
        service = get_experience_rag_service()

        # 사용자 입력을 하나의 쿼리로 결합
        query_parts = [payload.freeText]
        if payload.interests:
            query_parts.append(f"관심사: {', '.join(payload.interests)}")
        if payload.region:
            query_parts.append(f"지역: {payload.region}")

        query = " ".join(query_parts)

        response = service.recommend(db, query, payload.locale, limit=5)

        logger.info(
            "AI recommendation request completed",
            extra={
                "request_id": request_id,
                "experience_count": len(response.get("recommendedExperienceIds", [])),
            },
        )

        return {
            "answer": response["answer"],
            "recommendedExperienceIds": response["recommendedExperienceIds"],
            "reasons": response.get("reasons", {}),
            "matchingKeywords": response.get("matchingKeywords", []),
            "sources": response.get("sources", []),
            "fallback": False,
            "message": None,
        }

    except HTTPException as error:
        logger.warning(
            "AI recommendation request failed",
            extra={"request_id": request_id, "status_code": error.status_code},
        )
        # Fallback: 빈 추천 목록 반환
        return {
            "answer": "현재 AI 서비스와의 연결이 원활하지 않아요.",
            "recommendedExperienceIds": [],
            "reasons": {},
            "matchingKeywords": [],
            "sources": [],
            "fallback": True,
            "message": "AI 서비스가 일시적으로 불안정합니다.",
        }
    except Exception as error:
        logger.exception("AI recommendation failed unexpectedly", extra={"request_id": request_id})
        return {
            "answer": "현재 AI 서비스와의 연결이 원활하지 않아요.",
            "recommendedExperienceIds": [],
            "reasons": {},
            "matchingKeywords": [],
            "sources": [],
            "fallback": True,
            "message": "AI 서비스가 일시적으로 불안정합니다.",
        }
