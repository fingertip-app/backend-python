"""
일반 사용자 "내 예약 목록"용 Supabase JWT 검증.

이 Supabase 프로젝트는 액세스 토큰을 ES256(비대칭키)으로 서명한다. 따라서 공유 secret(HMAC)
대신, Supabase의 JWKS 공개키 엔드포인트에서 공개키를 받아 서명을 검증한다. DB 조회 없이
토큰의 sub(사용자 id)만 꺼내 쓴다. (구형 HS256 secret 방식도 폴백으로 함께 시도한다.)
"""

import logging
import secrets

import jwt
from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)

# JWKS 클라이언트는 공개키를 캐시하므로 매 요청마다 네트워크 호출하지 않는다. 1회만 생성.
_jwks_client: jwt.PyJWKClient | None = None


def _get_jwks_client() -> jwt.PyJWKClient | None:
    global _jwks_client
    if not settings.supabase_url:
        return None
    if _jwks_client is None:
        jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = jwt.PyJWKClient(jwks_url)
    return _jwks_client


def _decode(token: str) -> dict:
    # 1) ES256 (비대칭, JWKS) 우선
    client = _get_jwks_client()
    if client is not None:
        try:
            signing_key = client.get_signing_key_from_jwt(token)
            return jwt.decode(
                token,
                signing_key.key,
                algorithms=["ES256", "RS256"],
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as error:
            logger.debug("JWKS decode failed, will try HS fallback: %s", error)

    # 2) 구형 HS256 secret 폴백
    if settings.supabase_jwt_secret:
        try:
            return jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256", "HS384", "HS512"],
                options={"verify_aud": False},
            )
        except jwt.PyJWTError as error:
            logger.warning("Supabase JWT decode failed (HS fallback): %s", error)

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired token",
    )


def _is_configured() -> bool:
    return bool(settings.supabase_url or settings.supabase_jwt_secret)


def require_supabase_user_id(authorization: str | None = Header(None)) -> str:
    """'내 예약 목록'/'예약 생성' 처럼 로그인을 필수로 요구하는 엔드포인트용."""
    if not _is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase auth is not configured",
        )
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )
    token = authorization.split(" ", 1)[1]
    payload = _decode(token)
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing sub claim",
        )
    return user_id


def verify_chungbuk_admin_key(x_admin_key: str | None = Header(None)) -> None:
    """장인 인증(certify) 같은 관리자 전용 작업 보호. X-Admin-Key 헤더 검증."""
    if not settings.chungbuk_admin_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin key is not configured",
        )
    if not x_admin_key or not secrets.compare_digest(x_admin_key, settings.chungbuk_admin_key):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid admin key")
