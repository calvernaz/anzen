"""
Anzen Safety Gateway - Main Entry Point

FastAPI application with NeMo Guardrails and Presidio integration
for PII detection and masking in AI agent workflows.
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import AnzenGateway
# from .admin_api import AdminAPI  # Temporarily disabled due to dependencies
from .config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Anzen Safety Gateway",
        description="PII detection and masking for AI agents using NeMo Guardrails and Presidio",
        version="0.1.0",
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None,
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Initialize the safety gateway
    gateway = AnzenGateway(config_path=settings.config_path)

    # Initialize the admin API (temporarily disabled)
    # admin_api = AdminAPI()

    # Include the gateway routes
    app.include_router(gateway.router, prefix="/v1")
    # app.include_router(admin_api.router, prefix="/v1")

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "anzen-gateway"}

    return app


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Anzen Safety Gateway")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to")
    parser.add_argument("--config", help="Path to NeMo Guardrails config directory")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set config path if provided
    if args.config:
        import os

        os.environ["ANZEN_CONFIG_PATH"] = args.config

    # Create the app
    app = create_app()

    # Run the server
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level=args.log_level,
    )


if __name__ == "__main__":
    main()
