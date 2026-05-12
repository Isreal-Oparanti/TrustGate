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
    SQUAD_SECRET_KEY: str = ""
    SQUAD_MOCK_MODE: bool = True
    PAYMENT_CALLBACK_URL: str = "http://localhost:3000/payments/callback"
    PAYMENT_SECURITY_QUESTION: str = "What is your security answer?"
    PAYMENT_SECURITY_ANSWER: str = ""
    PAYMENT_SECURITY_ANSWER_HASH: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
