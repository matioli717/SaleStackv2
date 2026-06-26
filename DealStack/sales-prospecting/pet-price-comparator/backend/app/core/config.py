from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "pet-price-comparator"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    DATABASE_URL: str
    DATABASE_URL_SYNC: str

    REDIS_URL: str = "redis://localhost:6379/0"

    PLAYWRIGHT_HEADLESS: bool = True
    SCRAPER_CONCURRENCY: int = 3
    PROXY_URL: str | None = None

    PARTNER_WHATSAPP_NUMBER: str
    PARTNER_WEBHOOK_URL: str
    PARTNER_COMMISSION_PCT: float = 0.08
    PARTNER_MIN_MARGIN_PCT: float = 0.05

    SERPAPI_KEY: str | None = None
    AMAZON_PA_API_KEY: str | None = None
    AMAZON_PA_API_SECRET: str | None = None

    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()