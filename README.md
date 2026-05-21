# 장인과 하루 Backend

FastAPI 기반 API 서버 골격입니다. 기획서 기준 핵심 범위는 회원/장인/체험/예약/후기/카드뉴스/AI RAG/관리자 기능입니다.

## Stack

- FastAPI, Pydantic v2
- PostgreSQL + pgvector
- SQLAlchemy 2.x + Alembic
- Celery + Redis
- OpenAI API, LangChain
- Toss Payments webhook
- AWS S3, SES, Kakao AlimTalk

## Local Setup

```bash
cp .env.example .env
docker compose up -d
uvicorn app.main:app --reload
```

## Docker 사용 위치

초기 개발에서 Docker는 FastAPI 앱 자체보다 의존 인프라를 띄우는 데 사용합니다.

- `postgres`: PostgreSQL + pgvector. 서비스 데이터와 RAG 벡터 데이터를 저장합니다.
- `redis`: Celery 작업 큐, 임베딩/번역/알림 같은 비동기 작업에 사용합니다.

FastAPI 서버는 우선 로컬 Python 환경에서 실행합니다. 디버깅이 쉽고 코드 변경 반영이 빠르기 때문입니다. 배포/CI 단계에서 필요하면 FastAPI 서버용 `Dockerfile`을 추가합니다.

## 프로젝트 초기 설정

### 1. 환경변수 생성

```bash
cp .env.example .env
```

필수 값:

- `DATABASE_URL`: 로컬 Docker PostgreSQL 연결 문자열
- `REDIS_URL`: 로컬 Docker Redis 연결 문자열
- `JWT_SECRET`: 로컬 개발용 임의 문자열
- `OPENAI_API_KEY`: AI/RAG 기능 구현 시 필요
- `TOSS_SECRET_KEY`, `TOSS_WEBHOOK_SECRET`: 결제 구현 시 필요

### 2. DB/Redis 실행

```bash
docker compose up -d
docker compose ps
```

중지:

```bash
docker compose down
```

데이터까지 모두 삭제:

```bash
docker compose down -v
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

## Initial Routes

- `GET /health`
- `GET /api/v1/experiences`
- `GET /api/v1/cardnews`
- `POST /api/v1/ai/explain`
- `POST /api/v1/bookings`

세부 구현 항목은 [TODO.md](./TODO.md)를 기준으로 나눠 진행합니다.
