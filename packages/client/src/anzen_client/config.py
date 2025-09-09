"""
Anzen Client Configuration

Settings and configuration management.
"""

import os
from typing import List

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings."""

    # Server settings
    host: str = "0.0.0.0"
    port: int = 3000
    debug: bool = False

    # Service URLs
    agent_url: str = "http://localhost:8001"
    gateway_url: str = "http://localhost:8000"

    # CORS settings
    allowed_origins: List[str] = ["*"]

    # Logging
    log_level: str = "info"

    class Config:
        env_prefix = "ANZEN_"
        env_file = ".env"


def get_settings() -> Settings:
    """Get application settings."""
    return Settings()
