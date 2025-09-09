"""
Anzen AI Agent Configuration

Settings and configuration management.
"""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 8001
    debug: bool = False

    # Gateway settings
    gateway_url: str = "http://localhost:8000"
    gateway_api_key: str = ""

    # OpenAI settings
    openai_api_key: str = ""

    # CORS settings
    allowed_origins: List[str] = ["*"]

    # Database settings
    database_url: str = "sqlite:///./anzen_agent.db"

    # Logging
    log_level: str = "info"

    class Config:
        env_prefix = "ANZEN_"
        env_file = ".env"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
