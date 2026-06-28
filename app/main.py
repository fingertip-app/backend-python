from contextlib import asynccontextmanager
import logging
import uuid

from pathlib import Path

from fastapi import Depends, FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
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

    import os
    if os.environ.get("SKIP_DB_INIT") != "1":
        db = SessionLocal()
        try:
            CultureRagService.init_idf_cache(db)
        finally:
            db.close()
    else:
        logging.getLogger(__name__).warning(
            "SKIP_DB_INIT=1 - CultureRagService.init_idf_cache 건너뜀 (로컬 테스트용)"
        )

    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

_cors_origins = [
    origin.strip() for origin in settings.chungbuk_cors_origins.split(",") if origin.strip()
]
# 운영 도메인은 화이트리스트로, 로컬 개발(localhost/127.0.0.1 모든 포트)은 정규식으로 허용한다.
# Expo 개발 서버 포트가 매번 바뀌어도 CORS 막힘 없이 테스트할 수 있게 한다.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["*"],
    allow_headers=["*"],
)

# 충북 정적 이미지 서빙 (체험/장인/카드뉴스 사진). 코드와 함께 배포되는 읽기 전용 에셋.
_static_dir = Path(__file__).resolve().parent / "static"
_static_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(_static_dir)), name="static")

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