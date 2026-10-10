from functools import lru_cache
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# libpq-only URL options that asyncpg's connect() rejects with a TypeError.
_LIBPQ_ONLY_PARAMS = {"channel_binding"}


def normalize_database_url(url: str) -> str:
    """Turns a plain libpq-style URL (as handed out by Neon / Render) into
    one the SQLAlchemy asyncpg dialect accepts: swaps in the asyncpg driver,
    maps ?sslmode=X to ?ssl=X and drops libpq-only options. An explicit
    ?ssl= wins over ?sslmode=."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            url = "postgresql+asyncpg://" + url[len(prefix):]
            break

    parts = urlsplit(url)
    if not parts.query:
        return url
    params = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)]
    names = {k for k, _ in params}
    normalized = []
    for key, value in params:
        if key in _LIBPQ_ONLY_PARAMS:
            continue
        if key == "sslmode":
            if "ssl" in names:
                continue
            key = "ssl"
        normalized.append((key, value))
    return urlunsplit(parts._replace(query=urlencode(normalized)))


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

    # Where PDF-import artifacts (original PDFs, cropped question/option
    # images) live. "local" = filesystem under media_root (dev/tests);
    # "b2" = a PRIVATE Backblaze B2 bucket via its S3-compatible API.
    # Either way, nothing is a static route - everything is reachable only
    # through an authenticated endpoint.
    media_backend: Literal["local", "b2"] = "local"
    media_root: str = "./media"
    max_upload_mb: int = 20

    b2_endpoint_url: str = ""  # e.g. https://s3.us-west-004.backblazeb2.com
    b2_bucket: str = ""
    b2_key_id: str = ""
    b2_application_key: SecretStr = SecretStr("")
    b2_key_prefix: str = ""

    # The PDF import is memory-hungry (~550MB peak) so it is switched off on
    # the 512MB Render free instance; imports are run locally instead.
    imports_enabled: bool = True

    @field_validator("database_url")
    @classmethod
    def _normalize_database_url(cls, v: str) -> str:
        return normalize_database_url(v)

    @model_validator(mode="after")
    def _require_b2_settings(self) -> "Settings":
        if self.media_backend == "b2":
            missing = [
                name
                for name, value in (
                    ("B2_ENDPOINT_URL", self.b2_endpoint_url),
                    ("B2_BUCKET", self.b2_bucket),
                    ("B2_KEY_ID", self.b2_key_id),
                    ("B2_APPLICATION_KEY", self.b2_application_key.get_secret_value()),
                )
                if not value
            ]
            if missing:
                raise ValueError(f"MEDIA_BACKEND=b2 requires: {', '.join(missing)}")
        return self

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
