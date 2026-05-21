from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class BookingCreateRequest(BaseModel):
    experience_id: str
    date: str
    headcount: int
    message: str | None = None


@router.post("")
def create_booking(payload: BookingCreateRequest) -> dict[str, object]:
    # TODO(지현): 실시간 가용성 확인, 장인 알림, 결제 전 상태 생성을 구현한다.
    return {"id": "booking_draft_001", "status": "requested", **payload.model_dump()}
