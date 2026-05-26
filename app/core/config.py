from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    app_name: str = "장인과 하루 API"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://fingertip:fingertip@localhost:5432/fingertip"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret: str = "change-me-to-a-32-byte-local-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    openai_api_key: str = ""


settings = Settings()
