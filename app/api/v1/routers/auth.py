from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.v1.deps import get_current_active_user
from app.core.security import create_access_token
from app.db.models import User
from app.db.session import get_db
from app.schemas.auth import DevLoginRequest, TokenResponse, UserResponse

router = APIRouter()


@router.post("/dev-login", response_model=TokenResponse)
def dev_login(
    payload: DevLoginRequest,
    db: Annotated[Session, Depends(get_db)],
) -> TokenResponse:
    user = db.scalar(select(User).where(User.email == payload.email, User.provider == payload.provider))
    if user is None:
        user = User(
            email=payload.email,
            provider=payload.provider,
            nickname=payload.nickname,
            profile_image_url=payload.profile_image_url,
            is_active=True,
        )
        db.add(user)
    else:
        user.nickname = payload.nickname
        user.profile_image_url = payload.profile_image_url

    db.commit()
    db.refresh(user)

    access_token = create_access_token(
        subject=str(user.id),
        extra_claims={"email": user.email, "provider": user.provider},
    )
    return TokenResponse(access_token=access_token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def read_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
) -> User:
    return current_user
