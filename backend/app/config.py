"""Cấu hình đọc từ .env — dùng chung biến với bản Node."""
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str = "dev-only-secret"
    jwt_expires_in: str = "7d"
    port: int = 4000
    node_env: str = "development"
    client_url: str = "http://localhost:5173"
    app_url: str = "http://localhost:4000"
    resend_api_key: str = ""
    mail_from: str = ""
    google_client_id: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    ai_review_analysis: bool = False

    @field_validator("database_url")
    @classmethod
    def _strip_prisma_schema(cls, value: str) -> str:
        # Prisma thêm ?schema=public, libpq không hiểu tham số này.
        parts = urlsplit(value)
        query = [(k, v) for k, v in parse_qsl(parts.query) if k != "schema"]
        return urlunsplit(parts._replace(query=urlencode(query)))

    @property
    def is_development(self) -> bool:
        return self.node_env != "production"


settings = Settings()
