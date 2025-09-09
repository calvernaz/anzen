"""
Anzen Safety Gateway

A FastAPI-based safety gateway that uses NeMo Guardrails and Presidio
to detect and mask PII in AI agent inputs and outputs.
"""

__version__ = "0.1.0"
__author__ = "Anzen Team"
__email__ = "team@anzen.dev"

from .api import AnzenGateway
from .models import (EntityInfo, PolicyDecision, SafetyCheckRequest,
                     SafetyCheckResponse)

__all__ = [
    "AnzenGateway",
    "SafetyCheckRequest",
    "SafetyCheckResponse",
    "EntityInfo",
    "PolicyDecision",
]
