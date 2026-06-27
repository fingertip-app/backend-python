import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.db.chungbuk_models import ChungbukArtisan, ChungbukCardNews

router = APIRouter()
logger = logging.getLogger(__name__)


class ChungbukArtisanResponse(BaseModel):
    id: int
    name: str
    heritage_category: str
    certification_number: str | None = None
    is_chungbuk_certified: bool
    bio: str | None = None
    profile_image_url: str | None = None
    address: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ChungbukArtisanCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    heritage_category: str = Field(min_length=1, max_length=100)
    certification_number: str | None = Field(default=None, max_length=100)
    bio: str | None = None
    profile_image_url: str | None = None
    address: str | None = None


class ChungbukCardNewsResponse(BaseModel):
    id: int
    title: str
    content_type: str
    image_url: str | None = None
    ai_explanation: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ChungbukKpiResponse(BaseModel):
    chungbukCertifiedArtisanCount: int
    chungbukCardNewsCount: int
    chungbukHeritageItemCount: int


@router.get("/artisans", response_model=list[ChungbukArtisanResponse])
def list_chungbuk_artisans(db: Session = Depends(get_db)) -> list[ChungbukArtisan]:
    """충북 시도무형유산 보유자(장인) 목록 - 인증 완료된 장인만 노출"""
    stmt = select(ChungbukArtisan).where(ChungbukArtisan.is_chungbuk_certified.is_(True))
    return list(db.execute(stmt).scalars().all())


@router.post("/artisans", response_model=ChungbukArtisanResponse, status_code=status.HTTP_201_CREATED)
def register_chungbuk_artisan(
    payload: ChungbukArtisanCreateRequest, db: Session = Depends(get_db)
) -> ChungbukArtisan:
    """
    장인 등록 신청. 충북 시도무형유산 보유자 현황과의 자동대조 데이터가 없어
    is_chungbuk_certified는 항상 False(미인증)로 시작한다.
    관리자가 보유자 현황을 직접 대조한 뒤 /artisans/{id}/certify로 인증 처리한다.
    """
    artisan = ChungbukArtisan(
        name=payload.name,
        heritage_category=payload.heritage_category,
        certification_number=payload.certification_number,
        bio=payload.bio,
        profile_image_url=payload.profile_image_url,
        address=payload.address,
        is_chungbuk_certified=False,
    )
    db.add(artisan)
    db.commit()
    db.refresh(artisan)
    return artisan


@router.patch("/artisans/{artisan_id}/certify", response_model=ChungbukArtisanResponse)
def certify_chungbuk_artisan(artisan_id: int, db: Session = Depends(get_db)) -> ChungbukArtisan:
    """관리자가 충북 시도무형유산 보유자 현황을 직접 대조해 확인한 뒤 인증 처리"""
    artisan = db.get(ChungbukArtisan, artisan_id)
    if artisan is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Artisan not found")

    artisan.is_chungbuk_certified = True
    db.commit()
    db.refresh(artisan)
    return artisan


@router.get("/cardnews", response_model=list[ChungbukCardNewsResponse])
def list_chungbuk_card_news(db: Session = Depends(get_db)) -> list[ChungbukCardNews]:
    """한물결 카드뉴스 - 충북 연계 카테고리"""
    stmt = (
        select(ChungbukCardNews)
        .where(ChungbukCardNews.is_active.is_(True))
        .order_by(ChungbukCardNews.created_at.desc())
    )
    return list(db.execute(stmt).scalars().all())


@router.get("/kpi", response_model=ChungbukKpiResponse)
def get_chungbuk_kpi(db: Session = Depends(get_db)) -> ChungbukKpiResponse:
    """사업화 계획(3-2) 충북 한정 KPI 집계"""
    from app.db.chungbuk_models import ChungbukHeritageItem

    artisan_count = db.scalar(
        select(func.count()).select_from(ChungbukArtisan).where(ChungbukArtisan.is_chungbuk_certified.is_(True))
    )
    card_news_count = db.scalar(
        select(func.count()).select_from(ChungbukCardNews).where(ChungbukCardNews.is_active.is_(True))
    )
    heritage_count = db.scalar(select(func.count()).select_from(ChungbukHeritageItem))

    return ChungbukKpiResponse(
        chungbukCertifiedArtisanCount=artisan_count or 0,
        chungbukCardNewsCount=card_news_count or 0,
        chungbukHeritageItemCount=heritage_count or 0,
    )
