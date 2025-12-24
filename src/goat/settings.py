import os
from typing import Dict, TypeAlias

from dotenv import dotenv_values
from pydantic import Field, SecretStr, field_serializer
from pydantic_settings import BaseSettings, SettingsConfigDict


class CommonSettings(BaseSettings):
    # Application mode (development | production)
    APP_MODE: str = Field(default="development")

    model_config = SettingsConfigDict(env_file_encoding="utf-8", extra="forbid")


class DevSettings(CommonSettings):
    model_config = SettingsConfigDict(env_file=".env.dev")


class TestSettings(CommonSettings):
    USERNAME: str = Field(default="runner")

    model_config = SettingsConfigDict(env_file=".env.test")


class ProdSettings(CommonSettings):
    USERNAME: SecretStr
    PASSWORD: SecretStr
    model_config = SettingsConfigDict(env_file=".env")

    # NOTE: Careful with exposing secrets during serialization
    @field_serializer("USERNAME", "PASSWORD", when_used="json")
    def dump_secret(self, v):
        return v.get_secret_value()


# Type alias for all possible settings types
Settings: TypeAlias = DevSettings | TestSettings | ProdSettings | CommonSettings


def load_settings() -> Settings:
    """Load settings based on APP_MODE env var."""
    mode = os.getenv("APP_MODE", "development").lower()
    if mode in {"production", "prod"}:
        return ProdSettings()  # type: ignore[call-arg]
    if mode in {"test", "testing"}:
        return TestSettings()
    if mode in {"development", "dev"}:
        return DevSettings()
    return CommonSettings()


def get_source_map(settings: BaseSettings) -> Dict[str, str]:
    """
    Get a mapping of setting fields to their source (ENV, .env file, or Default). Only use this for debugging purposes.
    """
    env_file_vars = dotenv_values(settings.model_config["env_file"])  # type: ignore[arg-type]
    env_vars = os.environ
    source_map = {}

    for field in type(settings).model_fields:
        if field.upper() in env_vars:
            source_map[field] = "ENV"
        elif field.upper() in env_file_vars:
            source_map[field] = ".env file"
        else:
            source_map[field] = "Default"

    return source_map


if __name__ == "__main__":
    print("APP_MODE:", os.getenv("APP_MODE", "development"))
    settings = load_settings()
    print("Settings:", settings.model_dump())
    print("Source:", get_source_map(settings))
    print("Settings loaded successfully.")
    print("Settings - revealed:", settings.model_dump_json(indent=2))
