# CLAUDE.md — backend_python (FastAPI / Python)

---

## 기술 스택

```
프레임워크: FastAPI 0.115+
언어: Python 3.11+
패키지 매니저: uv
DB: PostgreSQL + SQLAlchemy 2.0 + Alembic
큐: Celery + Redis
AI: OpenAI API + LangChain
벡터 DB: pgvector
```

---

## 폴더 구조

```
app/
├── main.py          FastAPI 앱 진입점
├── api/             라우터 (엔드포인트)
│   └── v1/
├── core/            설정, 의존성, 보안
├── models/          SQLAlchemy 모델
├── schemas/         Pydantic 스키마 (요청/응답)
├── services/        비즈니스 로직
├── repositories/    DB 쿼리
└── workers/         Celery 태스크
```

---

## 코드 규칙

### 절대 하지 말 것
- 라우터에 비즈니스 로직 작성 금지 — services/ 로 분리
- ORM 모델을 API 응답으로 직접 반환 금지 — Pydantic 스키마 변환
- `print()` 금지 — `logging` 사용
- 동기 DB 쿼리 라우터에서 직접 호출 금지 — 의존성 주입 사용

### 반드시 지킬 것
- 클래스: PascalCase
- 함수/변수: snake_case
- 상수: SCREAMING_SNAKE_CASE
- 타입 힌트 모든 함수에 필수

---

## 패턴

```python
# Router — 얇게 유지
@router.post("/", response_model=schemas.ItemResponse)
async def create_item(
    data: schemas.ItemCreate,
    service: ItemService = Depends(get_item_service),
):
    return await service.create(data)

# Service — 비즈니스 로직
class ItemService:
    def __init__(self, repo: ItemRepository):
        self.repo = repo

    async def create(self, data: schemas.ItemCreate) -> schemas.ItemResponse:
        ...

# Schema — Pydantic v2
class ItemResponse(BaseModel):
    id: int
    name: str
    model_config = ConfigDict(from_attributes=True)
```

---

## Alembic 규칙

- 마이그레이션: `uv run alembic revision --autogenerate -m "[설명]"`
- 적용: `uv run alembic upgrade head`
- 기존 마이그레이션 파일 수정 금지

---

## AI / LangChain 관련

- 프롬프트 템플릿은 `app/prompts/` 에 분리
- OpenAI 호출은 반드시 에러 핸들링 + 재시도 로직 포함
- 토큰 비용 고려 — 불필요한 컨텍스트 포함 금지

---

## 자주 쓰는 커맨드

```bash
uv run uvicorn app.main:app --reload   # 개발 서버
uv run pytest                          # 테스트
uv run pytest tests/[파일명]           # 특정 테스트
uv run alembic upgrade head            # DB 마이그레이션
uv run celery -A app.workers worker    # Celery 워커
```
