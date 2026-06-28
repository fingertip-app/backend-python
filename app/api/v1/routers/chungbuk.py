import logging
import secrets
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.schemas.ai import ExplainResponse
from app.services.chungbuk.auth import (
    require_supabase_user_id,
    verify_chungbuk_admin_key,
)
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
TOURIST_SPOTS_FILE = "chungbuk_tourist_spots.json"


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
        # 장인 전용 대시보드(예약 확인) 접근용 고정 토큰. 정식 로그인 시스템은 아니지만
        # URL/엔드포인트를 안다고 아무나 다른 장인의 예약을 볼 수는 없게 막는다.
        "access_token": secrets.token_urlsafe(16),
    }
    artisans.append(artisan)
    write_json(ARTISANS_FILE, artisans)
    return artisan


@router.patch("/artisans/{artisan_id}/certify", response_model=ChungbukArtisanResponse)
def certify_chungbuk_artisan(artisan_id: int, _: None = Depends(verify_chungbuk_admin_key)) -> dict:
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
    supported_languages: list[str] = []
    category: str | None = None


class ChungbukExperienceCreateRequest(BaseModel):
    title: str = Field(min_length=1, max_length=255)
    description: str = ""
    price: int = Field(default=0, ge=0)
    duration_minutes: int = Field(default=60, ge=0)
    max_participants: int = Field(default=1, ge=1)
    image_url: str | None = None
    location: str | None = None
    supported_languages: list[str] = []
    category: str | None = None


@router.get("/experiences", response_model=list[ChungbukExperienceResponse])
def list_chungbuk_experiences() -> list[dict]:
    """충북 체험 프로그램 목록"""
    return read_json(EXPERIENCES_FILE)


@router.post(
    "/artisans/{artisan_id}/experiences",
    response_model=ChungbukExperienceResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_chungbuk_experience(
    artisan_id: int, token: str, payload: ChungbukExperienceCreateRequest
) -> dict:
    """장인이 본인 체험을 등록한다. 장인 토큰으로 보호하며 artisan_id에 귀속시킨다."""
    _verify_artisan_token(artisan_id, token)

    experiences = read_json(EXPERIENCES_FILE)
    experience = {
        "id": next_id(experiences),
        "title": payload.title,
        "description": payload.description,
        "artisan_id": artisan_id,
        "region": "충북",
        "price": payload.price,
        "duration_minutes": payload.duration_minutes,
        "max_participants": payload.max_participants,
        "image_url": payload.image_url,
        "location": payload.location,
        "supported_languages": payload.supported_languages,
        "category": payload.category,
    }
    experiences.append(experience)
    write_json(EXPERIENCES_FILE, experiences)
    return experience


def _find_experience(experiences: list[dict], experience_id: int) -> dict:
    for experience in experiences:
        if experience["id"] == experience_id:
            return experience
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found")


@router.patch(
    "/artisans/{artisan_id}/experiences/{experience_id}",
    response_model=ChungbukExperienceResponse,
)
def update_chungbuk_experience(
    artisan_id: int,
    experience_id: int,
    token: str,
    payload: ChungbukExperienceCreateRequest,
) -> dict:
    """장인이 본인 체험을 수정한다. 장인 토큰으로 보호하며 본인 소유 체험만 수정 가능."""
    _verify_artisan_token(artisan_id, token)

    experiences = read_json(EXPERIENCES_FILE)
    experience = _find_experience(experiences, experience_id)
    if experience.get("artisan_id") != artisan_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your experience")

    experience.update(
        {
            "title": payload.title,
            "description": payload.description,
            "price": payload.price,
            "duration_minutes": payload.duration_minutes,
            "max_participants": payload.max_participants,
            "image_url": payload.image_url,
            "location": payload.location,
            "supported_languages": payload.supported_languages,
            "category": payload.category,
        }
    )
    write_json(EXPERIENCES_FILE, experiences)
    return experience


@router.delete(
    "/artisans/{artisan_id}/experiences/{experience_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_chungbuk_experience(artisan_id: int, experience_id: int, token: str) -> None:
    """장인이 본인 체험을 삭제한다. 장인 토큰으로 보호하며 본인 소유 체험만 삭제 가능."""
    _verify_artisan_token(artisan_id, token)

    experiences = read_json(EXPERIENCES_FILE)
    experience = _find_experience(experiences, experience_id)
    if experience.get("artisan_id") != artisan_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your experience")

    experiences = [e for e in experiences if e["id"] != experience_id]
    write_json(EXPERIENCES_FILE, experiences)


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


# ---------- 주변 관광지 추천 ----------


class ChungbukTouristSpotResponse(BaseModel):
    id: int
    category: str
    region: str = "충북"
    sigun: str | None = None
    name: str
    address: str | None = None
    established_year: str | None = None
    open_cycle: str | None = None
    market_day: str | None = None
    note: str | None = None
    # 관광명소(tourInfo/attr.do) 전용 필드 - 전통시장 데이터에는 없어 null로 채워짐
    lat: str | None = None
    lng: str | None = None
    tour_type: str | None = None
    intro: str | None = None
    image_url: str | None = None
    hours: str | None = None
    tel: str | None = None
    url: str | None = None


@router.get("/tourist-spots", response_model=list[ChungbukTouristSpotResponse])
def list_chungbuk_tourist_spots(sigun: str | None = None) -> list[dict]:
    """
    체험 상세의 "주변 관광지 추천" 영역용 데이터.
    충북나드리 API는 접근 권한이 없어 한국관광공사 전통시장 Open API로 대체했다
    (scripts/fetch_chungbuk_tradimarket.py로 수집).
    sigun 쿼리파라미터로 특정 시군 주변만 필터링할 수 있다.
    """
    spots = read_json(TOURIST_SPOTS_FILE, default=[])
    if sigun:
        spots = [s for s in spots if s.get("sigun") == sigun]
    return spots


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
    num_participants: int = Field(default=1, ge=1, le=100)


class ChungbukReservationResponse(BaseModel):
    id: int
    experience_id: int
    user_name: str
    contact: str
    num_participants: int = 1
    total_price: int = 0
    status: str
    created_at: str
    user_id: str | None = None
    payment_key: str | None = None


@router.post(
    "/reservations", response_model=ChungbukReservationResponse, status_code=status.HTTP_201_CREATED
)
def create_chungbuk_reservation(
    payload: ChungbukReservationCreateRequest,
    user_id: str = Depends(require_supabase_user_id),
) -> dict:
    """
    체험 예약 신청 (데모용 - 결제/일정 관리 없이 신청 상태만 기록).
    로그인 필수 - Authorization 헤더에 유효한 Supabase JWT가 있어야 예약 가능하고,
    그 user_id로 "내 예약 목록"(GET /reservations/mine)에서 조회할 수 있다.
    """
    experiences = read_json(EXPERIENCES_FILE)
    experience = next((e for e in experiences if e["id"] == payload.experience_id), None)
    if experience is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found")

    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = {
        "id": next_id(reservations),
        "experience_id": payload.experience_id,
        "user_name": payload.user_name,
        "contact": payload.contact,
        "num_participants": payload.num_participants,
        "total_price": int(experience.get("price", 0)) * payload.num_participants,
        "status": "신청",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "user_id": user_id,
    }
    reservations.append(reservation)
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


@router.get("/reservations/mine", response_model=list[ChungbukReservationResponse])
def list_my_reservations(user_id: str = Depends(require_supabase_user_id)) -> list[dict]:
    """로그인한 사용자 본인이 신청한 예약 목록. Authorization: Bearer <supabase JWT> 필수."""
    reservations = read_json(RESERVATIONS_FILE, default=[])
    return [r for r in reservations if r.get("user_id") == user_id]


def _verify_artisan_token(artisan_id: int, token: str) -> dict:
    artisans = read_json(ARTISANS_FILE)
    for artisan in artisans:
        if artisan["id"] == artisan_id:
            if not secrets.compare_digest(artisan.get("access_token", ""), token):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid token")
            return artisan
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found")


@router.get("/artisans/{artisan_id}/reservations", response_model=list[ChungbukReservationResponse])
def list_artisan_reservations(artisan_id: int, token: str) -> list[dict]:
    """
    장인 전용 예약 확인. 정식 로그인(Supabase JWT) 검증 대신, 장인별 고정 토큰
    (access_token)으로 접근을 제한한다 - URL/엔드포인트를 안다고 아무나 다른 장인의
    예약을 보지 못하게 막는 최소한의 보호. 시간 압박으로 인한 임시 타협.
    """
    _verify_artisan_token(artisan_id, token)

    experiences = read_json(EXPERIENCES_FILE)
    my_experience_ids = {e["id"] for e in experiences if e.get("artisan_id") == artisan_id}

    reservations = read_json(RESERVATIONS_FILE, default=[])
    return [r for r in reservations if r["experience_id"] in my_experience_ids]


def _find_reservation(reservations: list[dict], reservation_id: int) -> dict:
    for reservation in reservations:
        if reservation["id"] == reservation_id:
            return reservation
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Reservation not found")


def _assert_artisan_owns_reservation(artisan_id: int, reservation: dict) -> None:
    experiences = read_json(EXPERIENCES_FILE)
    my_experience_ids = {e["id"] for e in experiences if e.get("artisan_id") == artisan_id}
    if reservation["experience_id"] not in my_experience_ids:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reservation")


@router.patch(
    "/artisans/{artisan_id}/reservations/{reservation_id}/approve",
    response_model=ChungbukReservationResponse,
)
def approve_chungbuk_reservation(artisan_id: int, reservation_id: int, token: str) -> dict:
    """장인이 본인 체험에 들어온 예약 신청을 승인(확정)한다."""
    _verify_artisan_token(artisan_id, token)
    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = _find_reservation(reservations, reservation_id)
    _assert_artisan_owns_reservation(artisan_id, reservation)

    reservation["status"] = "확정"
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


@router.patch(
    "/artisans/{artisan_id}/reservations/{reservation_id}/reject",
    response_model=ChungbukReservationResponse,
)
def reject_chungbuk_reservation(artisan_id: int, reservation_id: int, token: str) -> dict:
    """장인이 본인 체험에 들어온 예약 신청을 거절한다."""
    _verify_artisan_token(artisan_id, token)
    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = _find_reservation(reservations, reservation_id)
    _assert_artisan_owns_reservation(artisan_id, reservation)

    reservation["status"] = "거절"
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


@router.patch("/reservations/{reservation_id}/cancel", response_model=ChungbukReservationResponse)
def cancel_chungbuk_reservation(
    reservation_id: int, user_id: str = Depends(require_supabase_user_id)
) -> dict:
    """예약을 신청한 본인이 취소한다. 다른 사람의 예약은 취소할 수 없다."""
    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = _find_reservation(reservations, reservation_id)
    if reservation.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reservation")

    reservation["status"] = "취소"
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


@router.patch("/reservations/{reservation_id}/pay", response_model=ChungbukReservationResponse)
def pay_chungbuk_reservation(
    reservation_id: int, user_id: str = Depends(require_supabase_user_id)
) -> dict:
    """
    예약 결제 (데모용 - 실제 PG 연동 없이 결제 완료 상태만 기록).
    예약을 신청한 본인만 결제할 수 있고, 확정(승인)된 예약만 결제 가능하다.
    결제 완료 시 발급되는 payment_key를 QR 확인서 생성에 사용한다.
    """
    reservations = read_json(RESERVATIONS_FILE, default=[])
    reservation = _find_reservation(reservations, reservation_id)
    if reservation.get("user_id") != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your reservation")
    if reservation["status"] not in ("신청", "확정"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot pay a reservation with status '{reservation['status']}'",
        )

    reservation["status"] = "결제완료"
    reservation["payment_key"] = secrets.token_urlsafe(16)
    write_json(RESERVATIONS_FILE, reservations)
    return reservation


# ---------- 리뷰 ----------

REVIEWS_FILE = "chungbuk_reviews.json"


class ChungbukReviewCreateRequest(BaseModel):
    experience_id: int
    rating: int = Field(ge=1, le=5)
    content: str = Field(default="", max_length=2000)


class ChungbukReviewResponse(BaseModel):
    id: int
    experience_id: int
    user_id: str
    rating: int
    content: str
    created_at: str


@router.post("/reviews", response_model=ChungbukReviewResponse, status_code=status.HTTP_201_CREATED)
def create_chungbuk_review(
    payload: ChungbukReviewCreateRequest,
    user_id: str = Depends(require_supabase_user_id),
) -> dict:
    """체험 리뷰 작성. 로그인 필수."""
    experiences = read_json(EXPERIENCES_FILE)
    if not any(e["id"] == payload.experience_id for e in experiences):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found")

    reviews = read_json(REVIEWS_FILE, default=[])
    review = {
        "id": next_id(reviews),
        "experience_id": payload.experience_id,
        "user_id": user_id,
        "rating": payload.rating,
        "content": payload.content,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    reviews.append(review)
    write_json(REVIEWS_FILE, reviews)
    return review


@router.get("/reviews/experience/{experience_id}", response_model=list[ChungbukReviewResponse])
def list_chungbuk_experience_reviews(experience_id: int) -> list[dict]:
    """체험별 리뷰 목록 (공개, 로그인 불필요)."""
    reviews = read_json(REVIEWS_FILE, default=[])
    return [r for r in reviews if r.get("experience_id") == experience_id]


@router.get("/reviews/mine", response_model=list[ChungbukReviewResponse])
def list_my_chungbuk_reviews(user_id: str = Depends(require_supabase_user_id)) -> list[dict]:
    """로그인한 사용자 본인이 작성한 리뷰 목록 (중복 작성 여부 확인용)."""
    reviews = read_json(REVIEWS_FILE, default=[])
    return [r for r in reviews if r.get("user_id") == user_id]


# ---------- 찜(위시리스트) ----------

WISHLISTS_FILE = "chungbuk_wishlists.json"


class ChungbukWishlistResponse(BaseModel):
    id: int
    experience_id: int
    user_id: str
    created_at: str


@router.get("/wishlists", response_model=list[ChungbukWishlistResponse])
def list_my_chungbuk_wishlists(user_id: str = Depends(require_supabase_user_id)) -> list[dict]:
    """로그인한 사용자의 찜 목록."""
    wishlists = read_json(WISHLISTS_FILE, default=[])
    return [w for w in wishlists if w.get("user_id") == user_id]


@router.get("/wishlists/check/{experience_id}")
def check_chungbuk_wishlist(
    experience_id: int, user_id: str = Depends(require_supabase_user_id)
) -> dict:
    """특정 체험이 내 찜 목록에 있는지 확인."""
    wishlists = read_json(WISHLISTS_FILE, default=[])
    is_in_wishlist = any(
        w.get("user_id") == user_id and w.get("experience_id") == experience_id for w in wishlists
    )
    return {"isInWishlist": is_in_wishlist}


@router.post(
    "/wishlists/{experience_id}",
    response_model=ChungbukWishlistResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_chungbuk_wishlist(
    experience_id: int, user_id: str = Depends(require_supabase_user_id)
) -> dict:
    """체험을 찜 목록에 추가."""
    experiences = read_json(EXPERIENCES_FILE)
    if not any(e["id"] == experience_id for e in experiences):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Experience not found")

    wishlists = read_json(WISHLISTS_FILE, default=[])
    existing = next(
        (
            w
            for w in wishlists
            if w.get("user_id") == user_id and w.get("experience_id") == experience_id
        ),
        None,
    )
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Already in wishlist")

    wishlist = {
        "id": next_id(wishlists),
        "experience_id": experience_id,
        "user_id": user_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    wishlists.append(wishlist)
    write_json(WISHLISTS_FILE, wishlists)
    return wishlist


@router.delete("/wishlists/{experience_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_chungbuk_wishlist(
    experience_id: int, user_id: str = Depends(require_supabase_user_id)
) -> None:
    """체험을 찜 목록에서 제거."""
    wishlists = read_json(WISHLISTS_FILE, default=[])
    remaining = [
        w
        for w in wishlists
        if not (w.get("user_id") == user_id and w.get("experience_id") == experience_id)
    ]
    if len(remaining) == len(wishlists):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not in wishlist")
    write_json(WISHLISTS_FILE, remaining)


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
