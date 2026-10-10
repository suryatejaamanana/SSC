from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"
    database_url: str
    cors_origins: str = "http://localhost:3000"

    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Secure=True requires HTTPS; keep False for local http://localhost dev,
    # set True (via env) once the app is served over HTTPS in production.
    cookie_secure: bool = False
    cookie_samesite: str = "lax"

    # Local filesystem root for PDF-import storage (original PDFs, cropped
    # question/option images). Never mounted as a static route - everything
    # under it is only reachable through an authenticated endpoint.
    media_root: str = "./media"
    max_upload_mb: int = 20

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
