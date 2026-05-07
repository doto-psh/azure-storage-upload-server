from functools import lru_cache

from pydantic import Field, PositiveInt
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    azure_storage_account_name: str = Field(..., min_length=1)
    azure_storage_container_name: str = Field(..., min_length=1)
    azure_tenant_id: str | None = None
    azure_client_id: str | None = None
    azure_client_secret: str | None = None
    sas_ttl_minutes: PositiveInt = 15
    max_upload_bytes: PositiveInt = 5 * 1024 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
