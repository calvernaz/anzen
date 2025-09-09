"""
Anzen Safety Gateway API

FastAPI application for PII detection and masking using NeMo Guardrails and Presidio.
"""

import logging
import time
import uuid
from typing import Optional

from fastapi import APIRouter, HTTPException

from .presidio_actuator import PresidioActuator

logger = logging.getLogger(__name__)
# Try to import NeMo Guardrails, handle if not available
try:
    from nemoguardrails import LLMRails, RailsConfig

    NEMO_AVAILABLE = True
except Exception as e:
    logger.warning(f"NeMo Guardrails not available: {e}")
    NEMO_AVAILABLE = False

    # Mock classes for when NeMo is not available
    class LLMRails:
        def __init__(self, config):
            pass

        def register_action(self, *args, **kwargs):
            pass

        async def generate_async(self, *args, **kwargs):
            return {"role": "assistant", "content": "mock"}

    class RailsConfig:
        @staticmethod
        def from_path(path):
            return {}


from .models import EntityInfo, SafetyCheckRequest, SafetyCheckResponse

# Temporarily disable database dependencies for demo
# from .database import get_database_session, APIKey, User, Organization
# from .auth import validate_api_key
# from .audit import AuditLogger

logger = logging.getLogger(__name__)

# Using enhanced mock Presidio for demo (real Presidio requires spaCy models)
logger.info("Using enhanced mock Presidio for demo purposes")
PRESIDIO_AVAILABLE = False


class AnzenGateway:
    """Anzen Safety Gateway main class."""

    def __init__(self, config_path: str = "./config"):
        self.config_path = config_path
        self.router = APIRouter()
        self.rails: Optional[LLMRails] = None
        self.presidio = PresidioActuator()

        self._setup_rails()
        self._setup_routes()

    def _setup_rails(self):
        """Setup NeMo Guardrails with Presidio actions."""
        # Disable NeMo Guardrails for demo - use direct Presidio only
        logger.info("Demo mode: Using direct Presidio without NeMo Guardrails")
        self.rails = None

    def _assess_policy_decision(
        self, entities: list, risk_level: str, route: str
    ) -> str:
        """Assess policy decision based on entities, risk level, and route."""
        route_type = route.split(":")[0] if ":" in route else "public"

        # High-risk entities that should always be blocked in public routes
        high_risk_types = ["CREDIT_CARD", "US_SSN", "US_PASSPORT", "IBAN_CODE"]

        if route_type == "public":
            # Public routes: strict policy
            if risk_level == "high":
                return "BLOCK"
            elif any(entity["type"] in high_risk_types for entity in entities):
                return "BLOCK"
            elif risk_level == "medium":
                return "REDACT"
            else:
                return "ALLOW"

        elif route_type == "private":
            # Private routes: moderate policy
            if risk_level == "high" and any(
                entity["type"] in high_risk_types for entity in entities
            ):
                return "BLOCK"
            elif risk_level in ["high", "medium"]:
                return "REDACT"
            else:
                return "ALLOW"

        else:  # internal routes
            # Internal routes: permissive policy
            if any(entity["type"] in ["CREDIT_CARD", "US_SSN"] for entity in entities):
                return "REDACT"
            else:
                return "ALLOW"

    def _setup_routes(self):
        """Setup API routes."""

        @self.router.post("/anzen/check/input", response_model=SafetyCheckResponse)
        async def check_input(request: SafetyCheckRequest):
            """Check and mask input text for PII."""
            trace_id = str(uuid.uuid4())
            start_time = time.time()
            # Mock organization for demo
            organization = type(
                "obj", (object,), {"slug": "demo-org", "id": "demo-org-id"}
            )()
            user = type("obj", (object,), {"email": "demo@example.com"})()
            api_key = None

            try:
                logger.info(
                    f"Processing input check - trace_id: {trace_id}, org: {organization.slug}"
                )

                if self.rails:
                    # Use NeMo Guardrails for processing
                    result = await self.rails.generate_async(
                        messages=[{"role": "user", "content": request.text}]
                    )

                    # Extract results from NeMo execution context
                    entities = []
                    risk_level = "low"
                    safe_text = request.text

                    # Try to get results from NeMo context
                    if hasattr(self.rails, "runtime") and hasattr(
                        self.rails.runtime, "context"
                    ):
                        context_data = self.rails.runtime.context.get_data()
                        entities = context_data.get("entities", [])
                        risk_level = context_data.get("risk_level", "low")
                        safe_text = context_data.get("safe_text", request.text)

                    # If no results from NeMo, fall back to direct Presidio
                    if not entities:
                        entities = self.presidio.detect_pii(
                            request.text, request.language
                        )
                        risk_level = self._assess_risk_level(entities)

                else:
                    # Direct Presidio processing
                    entities = self.presidio.detect_pii(request.text, request.language)
                    risk_level = self._assess_risk_level(entities)
                    safe_text = request.text

                # Convert entities to our format
                entity_infos = [
                    EntityInfo(
                        type=e["type"],
                        start=e["start"],
                        end=e["end"],
                        score=e["score"],
                        text=e["text"],
                    )
                    for e in entities
                ]

                # Make policy decision
                decision = self._assess_policy_decision(
                    entities, risk_level, request.route
                )

                # Apply anonymization if needed
                if decision in ["REDACT", "BLOCK"]:
                    safe_text = self.presidio.anonymize_text(request.text, entities)

                # For BLOCK decisions, don't return the safe text
                if decision == "BLOCK":
                    safe_text = "[BLOCKED: Contains sensitive information]"

                response = SafetyCheckResponse(
                    decision=decision,
                    entities=entity_infos,
                    safe_text=safe_text,
                    risk_level=risk_level,
                    trace_id=trace_id,
                    metadata={
                        "route": request.route,
                        "language": request.language,
                        "entity_count": len(entities),
                        "processing_method": "nemo" if self.rails else "direct",
                        "organization": organization.slug,
                        "user": user.email,
                    },
                )

                # Audit logging (disabled for demo)
                # audit_logger = AuditLogger(db)
                # await self._log_audit_async(...)
                logger.info(f"Demo mode: audit logging disabled")

                logger.info(
                    f"Input check completed - decision: {decision}, entities: {len(entities)}, risk: {risk_level}"
                )
                return response

            except Exception as e:
                logger.error(f"Input check failed - trace_id: {trace_id}, error: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Safety check failed: {str(e)}"
                )

        @self.router.post("/anzen/check/output", response_model=SafetyCheckResponse)
        async def check_output(request: SafetyCheckRequest):
            """Check and mask output text for PII."""
            trace_id = str(uuid.uuid4())
            start_time = time.time()
            # Mock organization for demo
            organization = type(
                "obj", (object,), {"slug": "demo-org", "id": "demo-org-id"}
            )()
            user = type("obj", (object,), {"email": "demo@example.com"})()
            api_key = None

            try:
                logger.info(
                    f"Processing output check - trace_id: {trace_id}, org: {organization.slug}"
                )

                # For output, we always redact PII regardless of route
                entities = self.presidio.detect_pii(request.text, request.language)
                risk_level = self._assess_risk_level(entities)

                # Convert entities to our format
                entity_infos = [
                    EntityInfo(
                        type=e["type"],
                        start=e["start"],
                        end=e["end"],
                        score=e["score"],
                        text=e["text"],
                    )
                    for e in entities
                ]

                # Always redact PII in outputs
                decision = "REDACT" if entities else "ALLOW"
                safe_text = (
                    self.presidio.anonymize_text(request.text, entities)
                    if entities
                    else request.text
                )

                response = SafetyCheckResponse(
                    decision=decision,
                    entities=entity_infos,
                    safe_text=safe_text,
                    risk_level=risk_level,
                    trace_id=trace_id,
                    metadata={
                        "route": request.route,
                        "language": request.language,
                        "entity_count": len(entities),
                        "processing_method": "output_redaction",
                        "organization": organization.slug,
                        "user": user.email,
                    },
                )

                # Audit logging (disabled for demo)
                # audit_logger = AuditLogger(db)
                # await self._log_audit_async(...)
                logger.info(f"Demo mode: audit logging disabled")

                logger.info(
                    f"Output check completed - decision: {decision}, entities: {len(entities)}, risk: {risk_level}"
                )
                return response

            except Exception as e:
                logger.error(f"Output check failed - trace_id: {trace_id}, error: {e}")
                raise HTTPException(
                    status_code=500, detail=f"Safety check failed: {str(e)}"
                )

    def _assess_risk_level(self, entities: list) -> str:
        """Assess risk level based on detected entities."""
        if not entities:
            return "low"

        high_risk_entities = ["CREDIT_CARD", "US_SSN", "US_PASSPORT", "IBAN_CODE"]
        medium_risk_entities = ["EMAIL_ADDRESS", "PHONE_NUMBER", "PERSON"]

        # Check for high-risk entities
        for entity in entities:
            if entity["type"] in high_risk_entities and entity["score"] >= 0.8:
                return "high"

        # Check for medium-risk entities
        for entity in entities:
            if entity["type"] in medium_risk_entities and entity["score"] >= 0.6:
                return "medium"

        return "low"

    # Audit logging method disabled for demo
    # async def _log_audit_async(...): pass
