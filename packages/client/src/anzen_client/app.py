"""
Anzen Client Application

FastAPI application serving the React/Next.js frontend.
"""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates


class AnzenClient:
    """Anzen Client main class."""

    def __init__(self, agent_url: str, gateway_url: str):
        self.agent_url = agent_url
        self.gateway_url = gateway_url
        self.router = APIRouter()

        # Setup templates
        template_dir = Path(__file__).parent.parent.parent / "templates"
        self.templates = Jinja2Templates(directory=str(template_dir))

        self._setup_routes()

    def _setup_routes(self):
        """Setup API routes."""

        @self.router.get("/", response_class=HTMLResponse)
        async def chat_interface(request: Request):
            """Main chat interface."""
            return self.templates.TemplateResponse(
                "index.html", {"request": request, "title": "Anzen - Safe AI Chat"}
            )

        @self.router.get("/dashboard", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Legacy dashboard (for reference)."""
            return self.templates.TemplateResponse(
                "dashboard.html", {"request": request, "title": "Anzen Dashboard"}
            )

        @self.router.get("/api/config")
        async def get_config():
            """Get client configuration."""
            return {
                "agent_url": self.agent_url,
                "gateway_url": self.gateway_url,
                "version": "0.1.0",
            }
