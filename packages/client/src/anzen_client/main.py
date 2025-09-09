"""
Anzen Client - Main Entry Point

FastAPI application serving the React/Next.js frontend for the Anzen platform.
Provides web UI for secure AI agent interactions and compliance reporting.
"""

import argparse
import logging
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .app import AnzenClient
from .config import get_settings


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="Anzen Client",
        description="Web UI for Anzen Safe Agentic Workflows platform",
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

    # Mount static files
    static_dir = Path(__file__).parent.parent.parent / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Serve JavaScript files from templates directory
    templates_dir = Path(__file__).parent.parent.parent / "templates"

    @app.get("/dashboard.js")
    async def serve_dashboard_js():
        js_file = templates_dir / "dashboard.js"
        if js_file.exists():
            return FileResponse(js_file, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="JavaScript file not found")

    @app.get("/chat.js")
    async def serve_chat_js():
        js_file = templates_dir / "chat.js"
        if js_file.exists():
            return FileResponse(js_file, media_type="application/javascript")
        raise HTTPException(status_code=404, detail="JavaScript file not found")

    # Initialize the client
    client = AnzenClient(
        agent_url=settings.agent_url,
        gateway_url=settings.gateway_url,
    )

    # Include the client routes
    app.include_router(client.router)

    # Health check endpoint
    @app.get("/health")
    async def health_check():
        return {"status": "healthy", "service": "anzen-client"}

    return app


def main():
    """Main entry point for the CLI."""
    parser = argparse.ArgumentParser(description="Anzen Client")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=3000, help="Port to bind to")
    parser.add_argument("--agent-url", help="URL of the Anzen Agent")
    parser.add_argument("--gateway-url", help="URL of the Anzen Safety Gateway")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")

    args = parser.parse_args()

    # Configure logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Set URLs if provided
    if args.agent_url:
        import os

        os.environ["ANZEN_AGENT_URL"] = args.agent_url
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
