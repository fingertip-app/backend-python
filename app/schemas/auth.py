from pydantic import BaseModel, Field


class DevLoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    nickname: str = Field(min_length=1, max_length=100)
    provider: str = Field(default="dev", min_length=1, max_length=50)
    profile_image_url: str | None = None


class UserResponse(BaseModel):
    id: int
    email: str
    provider: str
    nickname: str
    profile_image_url: str | None = None
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse
