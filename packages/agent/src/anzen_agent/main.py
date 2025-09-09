"""
Anzen AI Agent - Main Entry Point

AI workflow agent with safety guardrails integration.
Implements a 2-step workflow: (1) plan → (2) execute with Wikipedia/Weather APIs.
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .agent import AnzenAgent
from .config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Anzen AI Agent",
        description="Secure AI agent with Plan → Execute workflow and safety guardrails",
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

    # Initialize the agent
    agent = AnzenAgent(
        gateway_url=settings.gateway_url,
        openai_api_key=settings.openai_api_key,
        gateway_api_key=settings.gateway_api_key,
    )

    # Include the agent routes
    app.include_router(agent.router, prefix="/v1")

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "anzen-agent"}

    return app


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Anzen AI Agent")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8001, help="Port to bind to")
    parser.add_argument("--gateway-url", help="URL of the Anzen Safety Gateway")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set gateway URL if provided
    if args.gateway_url:
        import os

        os.environ["ANZEN_GATEWAY_URL"] = args.gateway_url

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
