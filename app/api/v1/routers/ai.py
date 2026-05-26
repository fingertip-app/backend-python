from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.core.security import verify_internal_api_key

router = APIRouter(dependencies=[Depends(verify_internal_api_key)])


class ExplainRequest(BaseModel):
    query: str
    locale: str = "ko"


@router.post("/explain")
def explain_culture(payload: ExplainRequest) -> dict[str, object]:
    # TODO(영진, 서영): pgvector RAG 검색과 GPT 문화 해설 생성을 연결한다.
    return {
        "answer": f"'{payload.query}'와 관련된 전통문화 맥락을 준비 중입니다.",
        "sources": [],
        "recommendedExperienceIds": [],
    }
