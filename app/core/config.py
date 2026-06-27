from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 프로젝트 루트 기준 절대 경로. uvicorn을 어느 디렉토리에서 실행해도 동일한 위치를 가리킨다.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


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
    rag_candidate_k: int = 200
    rag_max_chunks_per_item: int = 3
    rag_context_max_chunks: int = 30
    rag_similarity_threshold: float = 0.20
    rag_vector_rank_weight: float = 0.7
    rag_lexical_rank_weight: float = 0.3
    internal_api_key: str = ""
    ai_fallback_enabled: bool = False
    ai_fallback_data_path: str = "app/data/ai_fallback_responses.json"
    chungbuk_cors_origins: str = ""
    # 코드 폴더 밖의 경로. git pull/배포 시 데이터가 덮어써지지 않도록 분리.
    # 운영(EC2): /var/lib/chungbuk-api/data, 로컬 개발: 기본값(repo 내 chungbuk_data) 사용
    chungbuk_data_dir: str = str(_PROJECT_ROOT / "chungbuk_data")


settings = Settings()
