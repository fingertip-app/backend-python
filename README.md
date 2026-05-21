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

## Initial Routes

- `GET /health`
- `GET /api/v1/experiences`
- `GET /api/v1/cardnews`
- `POST /api/v1/ai/explain`
- `POST /api/v1/bookings`

세부 구현 항목은 [TODO.md](./TODO.md)를 기준으로 나눠 진행합니다.
