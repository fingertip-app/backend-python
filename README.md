# 장인과 하루 FastAPI AI Server

FastAPI 기반 내부 AI 서버 골격입니다. 기획서 v4 기준으로 앱에 직접 노출되지 않으며, Spring Boot 메인 API 서버(`../backend`)가 내부 HTTP로 호출합니다.

## Responsibility Boundary

- 담당: 공공데이터 ETL, 임베딩/pgvector 검색, 문화 해설 RAG, 관련 체험 매칭, 번역, 후기 요약, 카드뉴스 AI 지원
- 비담당: 사용자 인증, 장인 승인, 예약 상태 전이, 결제 webhook, 앱 외부 API, 사용자 알림
- 데이터 정책: AI 벡터/ETL 스키마는 이 서버가 관리하고, 서비스 트랜잭션 데이터의 변경은 Spring API를 통해 처리합니다.

## Version

- App version: `0.1.0`
- Python: `3.11+`
- API status: 내부 AI API 초기 스캐폴드

## Stack

- FastAPI, Pydantic v2
- PostgreSQL + pgvector
- SQLAlchemy 2.x + Alembic
- Redis (필요 시 AI 배치/캐시)
- OpenAI API, LangChain

## Local Setup

```bash
cp .env.example .env
(cd ../backend && docker compose up -d)
uvicorn app.main:app --reload
```

## Docker 사용 위치

초기 개발에서 Docker는 FastAPI 앱 자체보다 AI 의존 인프라를 띄우는 데 사용합니다. Spring이 사용하는 서비스 DB와 충돌하지 않도록 공용 PostgreSQL/Redis 구성은 `../backend/docker-compose.yml`을 기준으로 맞춥니다.

- `postgres`: PostgreSQL + pgvector. RAG 벡터 데이터와 연동 조회에 사용합니다.
- `redis`: 임베딩/번역/요약 배치나 캐시가 필요할 때 사용합니다.

FastAPI 서버는 우선 로컬 Python 환경에서 실행합니다. 디버깅이 쉽고 코드 변경 반영이 빠르기 때문입니다. 배포/CI 단계에서 필요하면 FastAPI 서버용 `Dockerfile`을 추가합니다.

## 프로젝트 초기 설정

### 1. 환경변수 생성

```bash
cp .env.example .env
```

필수 값:

- `DATABASE_URL`: 로컬 Docker PostgreSQL 연결 문자열
- `REDIS_URL`: 로컬 Docker Redis 연결 문자열
- `OPENAI_API_KEY`: AI/RAG 기능 구현 시 필요
- `INTERNAL_API_KEY`: Spring 내부 호출 인증이 필요할 때 사용할 서버 간 키

### 2. DB/Redis 실행

```bash
(cd ../backend && docker compose up -d)
(cd ../backend && docker compose ps)
```

중지:

```bash
(cd ../backend && docker compose down)
```

데이터까지 모두 삭제:

```bash
(cd ../backend && docker compose down -v)
```

### 3. API 서버 실행

```bash
uvicorn app.main:app --reload
```

확인:

```bash
curl http://localhost:8000/health
```

### 4. 개발 체크

```bash
python -m compileall app
pytest
```

### 5. DB 마이그레이션 적용
새 마이그레이션이 머지된 경우 반드시 실행해야 합니다.

```bash
alembic upgrade head
```

검증:
```bash
python -c "from app.db.models import VectorDocument, EmbeddingMetadata; print('✅ 모델 import 성공')"
```

**⚠️ 주의**: 실행하지 않으면 테이블 구조가 맞지 않아 서버가 정상 동작하지 않습니다.


## Internal Routes

- `GET /health`
- `POST /api/v1/ai/explain`
- 구현 대상: `POST /api/v1/ai/translate`, `POST /api/v1/ai/reviews/summarize`, 임베딩 적재 배치 엔드포인트

`POST /api/v1/ai/explain`은 해설과 출처에 더해 `matchingKeywords`, `recommendedCategories`를 반환합니다. 실제 체험 조회와 ID 매핑은 Spring 메인 API가 자기 데이터에서 수행합니다.

인증, 체험, 카드뉴스, 예약 등 앱 외부 API 라우트와 서비스 도메인 모델은 v4 책임 범위에서 제거했습니다. FastAPI migration은 `heritage_items`와 vector 검색 인덱스만 관리합니다. 기존 초기 migration을 적용한 개발 DB가 있다면 AI DB를 재생성한 뒤 새 baseline을 적용해야 합니다.

세부 구현 항목과 2026-06-28 완료 일정은 [TODO.md](./TODO.md)를 기준으로 진행합니다.

## Smoke Test

### 벡터 유사도 검색 확인
```bash
python scripts/smoke_test.py
```

기대 결과:
- `=== 도자기 ===` → 유사도 0.30 이상 결과 반환
- `=== 존재하지 않는 키워드 ===` → "결과 없음" 출력

### 전체 테스트
```bash
pytest tests/
```
