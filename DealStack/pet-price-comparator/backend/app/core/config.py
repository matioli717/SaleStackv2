from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "pet-price-comparator"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"
    DATABASE_URL: str = "sqlite+aiosqlite:///:memory:"
    DATABASE_URL_SYNC: str = "sqlite:///:memory:"
    PARTNER_COMMISSION_PCT: float = 0.05
    PARTNER_MIN_MARGIN_PCT: float = 0.05
    PARTNER_WEBHOOK_URL: str = "http://localhost:8000/webhook/partner"
    SECRET_KEY: str = "dev-secret-key"
    REDIS_URL: str = "redis://localhost/0"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
