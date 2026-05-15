from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "TrustGate API"
    APP_ENV: str = "development"
    API_V1_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite:///./trustgate.db"
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10
    SQUAD_API_BASE_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_BASE_URL: str = "https://sandbox-api-d.squadco.com"
    SQUAD_SECRET_KEY: str = ""
    SQUAD_MOCK_MODE: bool = True
    NVIDIA_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    LLM_PROVIDER: str = "openai"
    EXTERNAL_VERIFICATION_ENABLED: bool = False
    IDENTITY_PROVIDER: str = "local"
    CAC_PROVIDER: str = "local"
    LLM_EXPLANATION_PROVIDER: str = "local_template"
    DOJAH_APP_ID: str = ""
    DOJAH_API_KEY: str = ""
    GOOGLE_MAPS_API_KEY: str = ""
    GOOGLE_API_KEY: str = ""
    GOOGLE_CX: str = ""
    ANTHROPIC_API_KEY: str = ""
    PREMBLY_API_KEY: str = ""
    TESSERACT_PATH: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
