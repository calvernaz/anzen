"""
Anzen Client

A React/Next.js frontend (served via FastAPI) for the Anzen Safe Agentic Workflows platform.
Provides a web UI for users to interact with secure AI agents and view compliance reports.
"""

__version__ = "0.1.0"
__author__ = "Anzen Team"
__email__ = "team@anzen.dev"

from .app import AnzenClient

__all__ = [
    "AnzenClient",
]
