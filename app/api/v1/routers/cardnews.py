from fastapi import APIRouter

router = APIRouter()


@router.get("")
def list_cardnews() -> list[dict[str, str]]:
    # TODO(영진): 공공 문화 데이터 + 트렌드 기반 카드뉴스 생성 결과를 연결한다.
    return [
        {
            "id": "card_embroidery_001",
            "title": "글로벌 K-콘텐츠 속 자수, 조선 왕실 기법입니다",
            "linkedExperienceId": "exp_embroidery_001",
        }
    ]
