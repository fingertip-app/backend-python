from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_experiences() -> list[dict[str, object]]:
    # TODO(지현): DB 연동 후 지역/날짜/가격/언어/난이도 필터를 추가한다.
    return [
        {
            "id": "exp_ceramic_001",
            "title": "달항아리 물레 체험",
            "category": "도자기",
            "region": "서울",
            "price": 65000,
            "artisanName": "국가 인증 장인",
        }
    ]
