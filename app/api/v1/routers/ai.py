from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.v1.deps import get_db
from app.core.security import verify_internal_api_key
from app.services.ai.rag import CultureRagService, get_culture_rag_service

router = APIRouter(dependencies=[Depends(verify_internal_api_key)])


class ExplainRequest(BaseModel):
    query: str = Field(min_length=1)
    locale: str = "ko"


class SourceResponse(BaseModel):
    id: int
    name: str
    source: str
    category: str | None = None


class ExplainResponse(BaseModel):
    answer: str
    sources: list[SourceResponse]
    matchingKeywords: list[str]
    recommendedCategories: list[str]


@router.post("/explain", response_model=ExplainResponse)
def explain_culture(
    payload: ExplainRequest,
    db: Session = Depends(get_db),
    service: CultureRagService = Depends(get_culture_rag_service),
) -> dict[str, Any]:
    return service.explain(db, payload.query, payload.locale)
