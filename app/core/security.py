from fastapi import Header, HTTPException, status

from app.core.config import settings


async def verify_internal_api_key(x_internal_api_key: str | None = Header(None)) -> str:
    if x_internal_api_key is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing X-Internal-Api-Key header",
        )

    if x_internal_api_key != settings.internal_api_key:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid X-Internal-Api-Key",
        )

    return x_internal_api_key
