import logging
from secrets import compare_digest

from fastapi import Header, HTTPException, status

from app.core.config import settings

logger = logging.getLogger(__name__)


async def verify_internal_api_key(x_internal_api_key: str | None = Header(None)) -> str:
    if not settings.internal_api_key:
        logger.error("Internal API key not configured")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal API authentication is not configured",
        )

    if x_internal_api_key is None:
        logger.warning("Missing X-Internal-Api-Key header")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Internal-Api-Key header",
        )

    if not compare_digest(x_internal_api_key, settings.internal_api_key):
        logger.warning("Invalid X-Internal-Api-Key")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Internal-Api-Key",
        )

    return x_internal_api_key
