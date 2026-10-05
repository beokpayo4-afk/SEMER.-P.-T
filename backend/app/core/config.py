from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(url: str) -> str:
    cleaned = url.strip()
    if not cleaned:
        raise RuntimeError("DATABASE_URL is not set")
    if cleaned.startswith("postgres://"):
        cleaned = "postgresql://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        cleaned = "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


class Settings(BaseSettings):
    app_name: str = "SEMER API"
    environment: str = "development"
    api_v1_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173"
    database_url: str = ""
    test_database_url: str = ""
    secret_key: str = ""
    access_token_expire_minutes: int = 30
    jwt_algorithm: str = "HS256"
    payment_provider: str = "manual"
    payment_currency: str = "INR"
    payment_webhook_secret: str = ""
    payment_key_id: str = ""
    payment_key_secret: str = ""
    image_storage: str = "local"
    image_upload_dir: str = ""
    image_max_bytes: int = 5_242_880
    image_public_prefix: str = "/uploads"
    image_s3_bucket: str = ""
    image_s3_endpoint: str = ""
    image_s3_region: str = ""
    image_s3_access_key: str = ""
    image_s3_secret_key: str = ""
    image_s3_public_base_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("access_token_expire_minutes", mode="before")
    @classmethod
    def default_token_minutes(cls, value: object) -> object:
        if value is None or value == "":
            return 30
        return value

    @field_validator("jwt_algorithm", mode="before")
    @classmethod
    def default_jwt_algorithm(cls, value: object) -> object:
        if value is None or value == "":
            return "HS256"
        if value != "HS256":
            raise ValueError("JWT_ALGORITHM must be HS256")
        return value

    @field_validator("payment_provider", mode="before")
    @classmethod
    def default_payment_provider(cls, value: object) -> object:
        if value is None or value == "":
            return "manual"
        return str(value).strip().lower()

    @field_validator("image_storage", mode="before")
    @classmethod
    def default_image_storage(cls, value: object) -> object:
        if value is None or value == "":
            return "local"
        cleaned = str(value).strip().lower()
        if cleaned not in {"local", "s3"}:
            raise ValueError("IMAGE_STORAGE must be local or s3")
        return cleaned

    @field_validator("image_max_bytes", mode="before")
    @classmethod
    def default_image_max_bytes(cls, value: object) -> object:
        if value is None or value == "":
            return 5_242_880
        return value

    @field_validator("payment_currency", mode="before")
    @classmethod
    def default_payment_currency(cls, value: object) -> object:
        if value is None or value == "":
            return "INR"
        cleaned = str(value).strip().upper()
        if len(cleaned) != 3 or not cleaned.isalpha():
            raise ValueError("PAYMENT_CURRENCY must be a 3-letter code")
        return cleaned

    @property
    def resolved_upload_dir(self) -> Path:
        if self.image_upload_dir.strip():
            return Path(self.image_upload_dir).expanduser().resolve()
        return Path(__file__).resolve().parents[2] / "uploads"

    @property
    def cors_origin_list(self) -> list[str]:
        origins = [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
        for origin in (
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://semer.vercel.app",
            "https://semer.in",
            "https://www.semer.in",
        ):
            if origin not in origins:
                origins.append(origin)
        return origins

    @property
    def sqlalchemy_database_url(self) -> str:
        return normalize_database_url(self.database_url)

    @property
    def sqlalchemy_test_database_url(self) -> str:
        return normalize_database_url(self.test_database_url.strip() or self.database_url)


settings = Settings()
