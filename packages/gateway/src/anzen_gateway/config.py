"""
Anzen Safety Gateway Configuration

Settings and configuration management.
"""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # NeMo Guardrails config
    config_path: str = "./config"

    # CORS settings
    allowed_origins: List[str] = ["*"]

    # Database settings
    database_url: str = "sqlite:///./anzen.db"

    # Redis settings
    redis_url: str = "redis://localhost:6379"

    # Logging
    log_level: str = "info"

    class Config:
        env_prefix = "ANZEN_"
        env_file = ".env"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
