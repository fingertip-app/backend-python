import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.schemas.ai import ExplainResponse
from app.services.chungbuk.data_store import next_id, read_json, write_json
from app.services.chungbuk.experience_recommend import (
    ChungbukExperienceRecommendService,
    get_chungbuk_experience_recommend_service,
)
from app.services.chungbuk.rag import ChungbukRagService, get_chungbuk_rag_service

router = APIRouter()
logger = logging.getLogger(__name__)

ARTISANS_FILE = "chungbuk_artisans.json"
EXPERIENCES_FILE = "chungbuk_experiences.json"
CARD_NEWS_FILE = "chungbuk_card_news.json"
RESERVATIONS_FILE = "chungbuk_reservations.json"


# ---------- 장인 ----------


class ChungbukArtisanResponse(BaseModel):
    id: int
    name: str
    heritage_category: str
    certification_number: str | None = None
    is_chungbuk_certified: bool
    bio: str | None = None
    profile_image_url: str | None = None
    address: str | None = None


class ChungbukArtisanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    heritage_category: str = Field(min_length=1, max_length=100)
    certification_number: str | None = None
    bio: str | None = None
    profile_image_url: str | None = None
    address: str | None = None


@router.get("/artisans", response_model=list[ChungbukArtisanResponse])
def list_chungbuk_artisans() -> list[dict]:
    """충북 시도무형유산 보유자(장인) 목록 - 인증 완료된 장인만 노출"""
    artisans = read_json(ARTISANS_FILE)
    return [a for a in artisans if a.get("is_chungbuk_certified")]


@router.post("/artisans", response_model=ChungbukArtisanResponse, status_code=status.HTTP_201_CREATED)
def register_chungbuk_artisan(payload: ChungbukArtisanCreateRequest) -> dict:
    """
    장인 등록 신청. 충북 시도무형유산 보유자 현황과의 자동대조 데이터가 없어
    is_chungbuk_certified는 항상 False(미인증)로 시작한다.
    관리자가 보유자 현황을 직접 대조한 뒤 /artisans/{id}/certify로 인증 처리한다.
    """
    artisans = read_json(ARTISANS_FILE)
    artisan = {
        "id": next_id(artisans),
        "name": payload.name,
        "heritage_category": payload.heritage_category,
        "certification_number": payload.certification_number,
        "is_chungbuk_certified": False,
        "bio": payload.bio,
        "profile_image_url": payload.profile_image_url,
        "address": payload.address,
    }
    artisans.append(artisan)
    write_json(ARTISANS_FILE, artisans)
    return artisan


@router.patch("/artisans/{artisan_id}/certify", response_model=ChungbukArtisanResponse)
def certify_chungbuk_artisan(artisan_id: int) -> dict:
    """관리자가 충북 시도무형유산 보유자 현황을 직접 대조해 확인한 뒤 인증 처리"""
    artisans = read_json(ARTISANS_FILE)
    for artisan in artisans:
        if artisan["id"] == artisan_id:
            artisan["is_chungbuk_certified"] = True
            write_json(ARTISANS_FILE, artisans)
            return artisan
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found")


# ---------- 체험 ----------


class ChungbukExperienceResponse(BaseModel):
    id: int
    title: str
    description: str
    artisan_id: int | None = None
    region: str = "충북"
    price: int
    duration_minutes: int
    max_participants: int
    image_url: str | None = None
    location: str | None = None


@router.get("/experiences", response_model=list[ChungbukExperienceResponse])
def list_chungbuk_experiences() -> list[dict]:
    """충북 체험 프로그램 목록"""
    return read_json(EXPERIENCES_FILE)


class ChungbukExperienceRecommendItem(ChungbukExperienceResponse):
    similarity: float


class ChungbukExperienceRecommendRequest(BaseModel):
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


def _get_chungbuk_experience_recommend_service_factory() -> (
    Callable[[], ChungbukExperienceRecommendService]
):
    return get_chungbuk_experience_recommend_service


@router.post("/experiences/recommend", response_model=list[ChungbukExperienceRecommendItem])
def recommend_chungbuk_experiences(
    payload: ChungbukExperienceRecommendRequest,
    service_factory: Callable[[], ChungbukExperienceRecommendService] = Depends(
        _get_chungbuk_experience_recommend_service_factory
    ),
) -> list[dict]:
    """
    체험 추천 (임베딩 유사도 검색). 동일 유사도 구간일 경우 region=충북 체험을 우선 노출한다.
    """
    service = service_factory()
    return service.recommend(payload.query, payload.top_k)


# ---------- 카드뉴스 ----------


class ChungbukCardNewsResponse(BaseModel):
    id: int
    title: str
    content_type: str
    image_url: str | None = None
    ai_explanation: str | None = None


@router.get("/cardnews", response_model=list[ChungbukCardNewsResponse])
def list_chungbuk_card_news() -> list[dict]:
    """한물결 카드뉴스 - 충북 연계 카테고리"""
    card_news = read_json(CARD_NEWS_FILE)
    return [c for c in card_news if c.get("is_active", True)]


# ---------- 예약 ----------


class ChungbukReservationCreateRequest(BaseModel):
    experience_id: int
    user_name: str = Field(min_length=1, max_length=100)
    contact: str = Field(min_length=1, max_length=100)


class ChungbukReservationResponse(BaseModel):
    id: int
    experience_id: int
    user_name: str
    contact: str
    status: str
    created_at: str


@router.post(
    "/reservations", response_model=ChungbukReservationResponse, status_code=status.HTTP_201_CREATED
)
def create_chungbuk_reservation(payload: ChungbukReservationCreateRequest) -> dict:
    """체험 예약 신청 (데모용 - 결제/일정 관리 없이 신청 상태만 기록)"""
    experiences = read_json(EXPERIENCES_FILE)
    if not any(e["id"] == payload.experience_id for e in experiences):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found")

    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = {
        "id": next_id(reservations),
        "experience_id": payload.experience_id,
        "user_name": payload.user_name,
        "contact": payload.contact,
        "status": "신청",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reservations.append(reservation)
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


@router.get("/reservations", response_model=list[ChungbukReservationResponse])
def list_chungbuk_reservations() -> list[dict]:
    return read_json(RESERVATIONS_FILE, default=[])


# ---------- KPI ----------


class ChungbukKpiResponse(BaseModel):
    chungbukCertifiedArtisanCount: int
    chungbukExperienceCount: int
    chungbukCardNewsCount: int
    chungbukReservationCount: int


@router.get("/kpi", response_model=ChungbukKpiResponse)
def get_chungbuk_kpi() -> ChungbukKpiResponse:
    """사업화 계획(3-2) 충북 한정 KPI 집계"""
    artisans = read_json(ARTISANS_FILE)
    experiences = read_json(EXPERIENCES_FILE)
    card_news = read_json(CARD_NEWS_FILE)
    reservations = read_json(RESERVATIONS_FILE, default=[])

    return ChungbukKpiResponse(
        chungbukCertifiedArtisanCount=sum(1 for a in artisans if a.get("is_chungbuk_certified")),
        chungbukExperienceCount=len(experiences),
        chungbukCardNewsCount=sum(1 for c in card_news if c.get("is_active", True)),
        chungbukReservationCount=len(reservations),
    )


# ---------- AI 챗봇 ----------


class ChungbukAiExplainRequest(BaseModel):
    query: str = Field(min_length=1, max_length=5000)
    locale: str = Field(default="ko")


def _get_chungbuk_rag_service_factory() -> Callable[[], ChungbukRagService]:
    return get_chungbuk_rag_service


@router.post("/ai/explain", response_model=ExplainResponse)
def explain_chungbuk_heritage(
    payload: ChungbukAiExplainRequest,
    request: Request,
    service_factory: Callable[[], ChungbukRagService] = Depends(_get_chungbuk_rag_service_factory),
) -> dict[str, Any]:
    """충북 시도무형유산 전용 AI 챗봇 - chungbuk_heritage.json만 참고해 답변"""
    request_id = getattr(request.state, "request_id", None)
    logger.info("Chungbuk AI explain request started", extra={"request_id": request_id})
    try:
        service = service_factory()
        return service.explain(payload.query, payload.locale)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Chungbuk AI explain failed unexpectedly", extra={"request_id": request_id})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI service unavailable",
        )
