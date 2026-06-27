"""
일반 사용자 "내 예약 목록"용 Supabase JWT 검증.

손끝과 같은 Supabase 프로젝트의 Auth를 그대로 쓰기로 했으므로, 로그인/회원가입은
프론트가 Supabase SDK로 직접 처리하고 우리는 프론트가 보내주는 JWT의 서명만
검증해서 "이 토큰의 주인이 누구인지(sub)"만 꺼내 쓴다. DB 조회 없이 서명 검증만
하는 가벼운 작업이라 JSON 기반 구조에도 문제없이 들어간다.
"""

import logging

import jwt
from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


def _decode(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.supabase_jwt_secret,
            algorithms=["HS256"],
            options={"verify_aud": False},
        )
    except jwt.PyJWTError as error:
        logger.warning("Supabase JWT decode failed: %s", error)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from error


def get_optional_supabase_user_id(authorization: str | None = Header(None)) -> str | None:
    """로그인 안 했어도 통과시킨다 (예약은 비로그인도 가능). 토큰이 있으면 검증해서 sub를 꺼낸다."""
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    if not settings.supabase_jwt_secret:
        return None
    token = authorization.split(" ", 1)[1]
    payload = _decode(token)
    return payload.get("sub")


def require_supabase_user_id(authorization: str | None = Header(None)) -> str:
    """'내 예약 목록' 처럼 로그인을 필수로 요구하는 엔드포인트용."""
    if not settings.supabase_jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase JWT verification is not configured",
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
