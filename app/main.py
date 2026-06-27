from contextlib import asynccontextmanager
import logging
import uuid

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.v1 import deps
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import SessionLocal
from app.services.ai.rag import CultureRagService

logger = logging.getLogger(__name__)

# 로그에 기록할 최대 바디 길이 (바이트)
MAX_BODY_LOG_LENGTH = 1024


def _get_safe_body_preview(body_bytes: bytes) -> str:
    """
    요청 본문을 안전하게 로깅하기 위해 truncate 처리.
    민감 정보 노출 방지 및 로그 볼륨 제어.
    """
    if len(body_bytes) > MAX_BODY_LOG_LENGTH:
        preview = body_bytes[:MAX_BODY_LOG_LENGTH].decode("utf-8", errors="replace")
        return f"{preview}...[truncated, total: {len(body_bytes)} bytes]"
    return body_bytes.decode("utf-8", errors="replace")


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()

    db = SessionLocal()
    try:
        CultureRagService.init_idf_cache(db)
    finally:
        db.close()

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

if settings.chungbuk_cors_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[origin.strip() for origin in settings.chungbuk_cors_origins.split(",")],
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    request_id = getattr(request.state, "request_id", None)

    # Body를 안전하게 읽기 (이미 소비되었을 수 있음)
    try:
        body_bytes = await request.body()
        body_preview = _get_safe_body_preview(body_bytes)
    except Exception:
        body_preview = "[body read failed]"

    # errors()를 직렬화 안전하게 처리
    error_details = str(exc.errors())

    logger.warning(
        "Request validation failed",
        extra={
            "request_id": request_id,
            "error_count": len(exc.errors()),
            "error_details": error_details,
            "body_preview": body_preview,
        },
    )
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "success": False,
            "message": "AI query validation failed",
            "errorCode": "INVALID_REQUEST",
            "details": exc.errors(),
        },
    )


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


@app.get("/health")
def health(db: Session = Depends(deps.get_db)) -> JSONResponse:
    checks = {
        "db": "ok",
        "ai": "configured" if settings.openai_api_key else "missing_openai_api_key",
        "fallback": "enabled" if settings.ai_fallback_enabled else "disabled",
    }

    try:
        db.execute(text("SELECT 1"))
    except Exception:
        checks["db"] = "error"
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "degraded", "checks": checks},
        )

    status_code = (
        status.HTTP_200_OK
        if checks["ai"] == "configured"
        else status.HTTP_503_SERVICE_UNAVAILABLE
    )
    overall_status = "ok" if status_code == status.HTTP_200_OK else "degraded"
    return JSONResponse(status_code=status_code, content={"status": overall_status, "checks": checks})