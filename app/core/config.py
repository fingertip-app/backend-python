from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "장인과 하루 API"
    app_env: str = "local"
    database_url: str = "postgresql+psycopg://fingertip:fingertip@localhost:5432/fingertip"
    redis_url: str = "redis://localhost:6379/0"
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_generation_model: str = "gpt-4o-mini"
    rag_locale_fallback: str = "ko"
    rag_top_k: int = 20
    rag_candidate_k: int = 100
    rag_context_max_chunks: int = 30
    rag_similarity_threshold: float = 0.20
    internal_api_key: str = ""
    ai_fallback_enabled: bool = False
    ai_fallback_data_path: str = "app/data/ai_fallback_responses.json"


settings = Settings()
