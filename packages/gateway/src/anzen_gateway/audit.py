"""
Audit logging service for Anzen Gateway

Compliance-focused logging with data minimization and privacy protection.
"""

import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from .database import AuditLog, Organization

logger = logging.getLogger(__name__)


class AuditLogger:
    """Audit logging service with privacy protection."""

    def __init__(self, db: Session):
        self.db = db

    def log_safety_check(
        self,
        trace_id: str,
        organization_id: str,
        route: str,
        method: str,  # "input" or "output"
        input_text: str,
        output_text: Optional[str],
        entities: List[Dict[str, Any]],
        risk_level: str,
        decision: str,
        processing_time_ms: float,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AuditLog:
        """
        Log a safety check event with privacy protection.

        Args:
            trace_id: Unique trace identifier
            organization_id: Organization UUID
            route: Route classification (e.g., "public:chat")
            method: "input" or "output"
            input_text: Original input text
            output_text: Output text (if applicable)
            entities: Detected PII entities
            risk_level: Risk assessment (low/medium/high)
            decision: Policy decision (ALLOW/BLOCK/REDACT)
            processing_time_ms: Processing time in milliseconds
            session_id: Optional session identifier
            metadata: Additional metadata

        Returns:
            Created audit log record
        """
        try:
            # Hash text for privacy (no raw PII stored)
            input_hash = self._hash_text(input_text)
            output_hash = self._hash_text(output_text) if output_text else None

            # Extract entity types only (no actual PII text)
            entity_types = [entity.get("type", "UNKNOWN") for entity in entities]

            # Create audit log entry
            audit_log = AuditLog(
                trace_id=trace_id,
                session_id=session_id,
                organization_id=organization_id,
                route=route,
                method=method,
                entities_detected=entity_types,
                entity_count=len(entities),
                risk_level=risk_level,
                decision=decision,
                input_hash=input_hash,
                output_hash=output_hash,
                text_length=len(input_text),
                processing_time_ms=processing_time_ms,
                extra_metadata=metadata or {},
            )

            self.db.add(audit_log)
            self.db.commit()
            self.db.refresh(audit_log)

            logger.info(f"Audit log created: {trace_id} - {decision} ({risk_level})")
            return audit_log

        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
            self.db.rollback()
            raise

    def get_compliance_report(
        self,
        organization_id: str,
        start_date: datetime,
        end_date: datetime,
        route_filter: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Generate a compliance report for an organization.

        Args:
            organization_id: Organization UUID
            start_date: Report start date
            end_date: Report end date
            route_filter: Optional route filter (e.g., "public:*")

        Returns:
            Compliance report data
        """
        try:
            # Base query
            query = self.db.query(AuditLog).filter(
                AuditLog.organization_id == organization_id,
                AuditLog.created_at >= start_date,
                AuditLog.created_at <= end_date,
            )

            # Apply route filter if provided
            if route_filter:
                if route_filter.endswith("*"):
                    route_prefix = route_filter[:-1]
                    query = query.filter(AuditLog.route.like(f"{route_prefix}%"))
                else:
                    query = query.filter(AuditLog.route == route_filter)

            logs = query.all()

            # Calculate metrics
            total_requests = len(logs)
            blocked_requests = len([log for log in logs if log.decision == "BLOCK"])
            redacted_requests = len([log for log in logs if log.decision == "REDACT"])
            allowed_requests = len([log for log in logs if log.decision == "ALLOW"])

            # PII type analysis
            pii_types = {}
            for log in logs:
                for entity_type in log.entities_detected:
                    pii_types[entity_type] = pii_types.get(entity_type, 0) + 1

            # Route analysis
            routes = {}
            for log in logs:
                route = log.route
                if route not in routes:
                    routes[route] = {
                        "total": 0,
                        "blocked": 0,
                        "redacted": 0,
                        "allowed": 0,
                    }
                routes[route]["total"] += 1
                routes[route][log.decision.lower()] += 1

            # Risk level analysis
            risk_levels = {"low": 0, "medium": 0, "high": 0}
            for log in logs:
                risk_levels[log.risk_level] = risk_levels.get(log.risk_level, 0) + 1

            # Performance metrics
            processing_times = [
                log.processing_time_ms for log in logs if log.processing_time_ms
            ]
            avg_processing_time = (
                sum(processing_times) / len(processing_times) if processing_times else 0
            )

            report = {
                "period": {
                    "start": start_date.isoformat(),
                    "end": end_date.isoformat(),
                },
                "summary": {
                    "total_requests": total_requests,
                    "blocked_requests": blocked_requests,
                    "redacted_requests": redacted_requests,
                    "allowed_requests": allowed_requests,
                    "block_rate": (
                        blocked_requests / total_requests if total_requests > 0 else 0
                    ),
                    "redaction_rate": (
                        redacted_requests / total_requests if total_requests > 0 else 0
                    ),
                },
                "pii_types": pii_types,
                "routes": routes,
                "risk_levels": risk_levels,
                "performance": {
                    "avg_processing_time_ms": avg_processing_time,
                    "total_processing_time_ms": sum(processing_times),
                },
            }

            logger.info(
                f"Generated compliance report for org {organization_id}: {total_requests} requests"
            )
            return report

        except Exception as e:
            logger.error(f"Failed to generate compliance report: {e}")
            raise

    def get_recent_logs(
        self, organization_id: str, limit: int = 100, route_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get recent audit logs for an organization.

        Args:
            organization_id: Organization UUID
            limit: Maximum number of logs to return
            route_filter: Optional route filter

        Returns:
            List of recent audit logs (sanitized)
        """
        try:
            query = (
                self.db.query(AuditLog)
                .filter(AuditLog.organization_id == organization_id)
                .order_by(AuditLog.created_at.desc())
                .limit(limit)
            )

            if route_filter:
                if route_filter.endswith("*"):
                    route_prefix = route_filter[:-1]
                    query = query.filter(AuditLog.route.like(f"{route_prefix}%"))
                else:
                    query = query.filter(AuditLog.route == route_filter)

            logs = query.all()

            # Sanitize logs (remove hashes, keep only metadata)
            sanitized_logs = []
            for log in logs:
                sanitized_log = {
                    "id": str(log.id),
                    "trace_id": log.trace_id,
                    "route": log.route,
                    "method": log.method,
                    "entities_detected": log.entities_detected,
                    "entity_count": log.entity_count,
                    "risk_level": log.risk_level,
                    "decision": log.decision,
                    "text_length": log.text_length,
                    "processing_time_ms": log.processing_time_ms,
                    "created_at": log.created_at.isoformat(),
                    "metadata": log.extra_metadata,
                }
                sanitized_logs.append(sanitized_log)

            return sanitized_logs

        except Exception as e:
            logger.error(f"Failed to get recent logs: {e}")
            raise

    @staticmethod
    def _hash_text(text: str) -> str:
        """Hash text using SHA-256 for privacy protection."""
        if not text:
            return ""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()


class AuditMiddleware:
    """Middleware for automatic audit logging."""

    def __init__(self, audit_logger: AuditLogger):
        self.audit_logger = audit_logger

    async def log_request(
        self,
        trace_id: str,
        organization_id: str,
        route: str,
        method: str,
        input_text: str,
        output_text: Optional[str],
        entities: List[Dict[str, Any]],
        risk_level: str,
        decision: str,
        start_time: float,
        session_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Log a request asynchronously."""
        processing_time_ms = (time.time() - start_time) * 1000

        try:
            self.audit_logger.log_safety_check(
                trace_id=trace_id,
                organization_id=organization_id,
                route=route,
                method=method,
                input_text=input_text,
                output_text=output_text,
                entities=entities,
                risk_level=risk_level,
                decision=decision,
                processing_time_ms=processing_time_ms,
                session_id=session_id,
                metadata=metadata,
            )
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")
            # Don't fail the request if audit logging fails
