"""
Anzen Safety Gateway Models

Pydantic models for API requests and responses.
"""

from typing import List, Optional

from pydantic import BaseModel


class EntityInfo(BaseModel):
    """Information about a detected PII entity."""

    type: str
    start: int
    end: int
    score: float
    text: str


class SafetyCheckRequest(BaseModel):
    """Request model for safety checks."""

    text: str
    route: str = "public:chat"
    language: str = "en"
    user_id: Optional[str] = None
    session_id: Optional[str] = None


class SafetyCheckResponse(BaseModel):
    """Response model for safety checks."""

    decision: str  # ALLOW, BLOCK, REDACT
    entities: List[EntityInfo] = []
    safe_text: str = ""
    risk_level: str = "low"  # low, medium, high
    trace_id: Optional[str] = None
    metadata: dict = {}


class PolicyDecision(BaseModel):
    """Policy decision details."""

    action: str  # allow, block, redact
    reason: str
    confidence: float
    policy_name: str
