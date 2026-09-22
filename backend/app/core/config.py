from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL
from sqlalchemy.engine import make_url


class Settings(BaseSettings):
    app_name: str = "Traffic AI"
    app_env: str = "development"
    postgres_db: str = "traffic_ai_db"
    postgres_user: str = "traffic_admin"
    postgres_password: str = "TrafficAI@2026"
    postgres_host: str = "postgres"
    postgres_port: int = 5432
    ai_service_url: str = "http://ai-service:8001"
    ai_shared_token: str = "TrafficAI-Local-2026"
    database_url_override: str | None = None

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def database_url(self) -> URL:
        if self.database_url_override:
            return make_url(self.database_url_override)
        return URL.create(
            drivername="postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
