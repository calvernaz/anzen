"""
Simple database models for Anzen Gateway (SQLite compatible)

Simplified models that work with SQLite for demo purposes.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

logger = logging.getLogger(__name__)

Base = declarative_base()


class Organization(Base):
    """Organization/tenant model."""

    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    is_active = Column(Boolean, default=True)


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class APIKey(Base):
    """API key model."""

    __tablename__ = "api_keys"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)
    key_prefix = Column(String(20), nullable=False)
    user_id = Column(String(36), ForeignKey("users.id"), nullable=False)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True)
    usage_count = Column(Integer, default=0)


class AuditLog(Base):
    """Audit log model."""

    __tablename__ = "audit_logs"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    trace_id = Column(String(100), nullable=False, index=True)
    organization_id = Column(String(36), ForeignKey("organizations.id"), nullable=False)
    route = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)
    entity_count = Column(Integer, default=0)
    risk_level = Column(String(20), nullable=False)
    decision = Column(String(20), nullable=False)
    input_hash = Column(String(64), nullable=True)
    text_length = Column(Integer, nullable=False)
    processing_time_ms = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SimpleDatabaseManager:
    """Simple database manager for demo."""

    def __init__(self, database_url: str = "sqlite:///anzen_demo.db"):
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def create_tables(self):
        """Create all database tables."""
        Base.metadata.create_all(bind=self.engine)
        logger.info("Database tables created")

    def get_session(self) -> Session:
        """Get a database session."""
        return self.SessionLocal()

    def close(self):
        """Close database connections."""
        self.engine.dispose()


def create_simple_user(
    email: str,
    name: str,
    password: str,
    organization_id: str,
    db: Session,
    is_admin: bool = False,
) -> User:
    """Create a simple user."""
    from packages.gateway.src.anzen_gateway.auth import AuthManager

    # Check if user exists
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        return existing

    # Create user
    hashed_password = AuthManager.get_password_hash(password)
    user = User(
        email=email,
        name=name,
        hashed_password=hashed_password,
        organization_id=organization_id,
        is_admin=is_admin,
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def create_simple_api_key(
    name: str, user_id: str, organization_id: str, db: Session
) -> tuple:
    """Create a simple API key."""
    from packages.gateway.src.anzen_gateway.auth import AuthManager

    # Generate key
    full_key, key_hash, key_prefix = AuthManager.generate_api_key()

    # Create record
    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        user_id=user_id,
        organization_id=organization_id,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    return full_key, api_key


def log_simple_audit(
    db: Session,
    trace_id: str,
    organization_id: str,
    route: str,
    method: str,
    text: str,
    entities: List[Dict],
    risk_level: str,
    decision: str,
    processing_time: float,
):
    """Log a simple audit entry."""
    import hashlib

    # Hash text for privacy
    input_hash = hashlib.sha256(text.encode()).hexdigest()

    # Extract entity types
    entity_types = [e.get("type", "UNKNOWN") for e in entities]

    audit_log = AuditLog(
        trace_id=trace_id,
        organization_id=organization_id,
        route=route,
        method=method,
        entity_count=len(entities),
        risk_level=risk_level,
        decision=decision,
        input_hash=input_hash,
        text_length=len(text),
        processing_time_ms=processing_time,
    )

    db.add(audit_log)
    db.commit()
    db.refresh(audit_log)

    return audit_log


def get_simple_compliance_report(db: Session, organization_id: str) -> Dict[str, Any]:
    """Get a simple compliance report."""
    logs = db.query(AuditLog).filter(AuditLog.organization_id == organization_id).all()

    total = len(logs)
    blocked = len([log for log in logs if log.decision == "BLOCK"])
    redacted = len([log for log in logs if log.decision == "REDACT"])
    allowed = len([log for log in logs if log.decision == "ALLOW"])

    # Risk level breakdown
    risk_levels = {"low": 0, "medium": 0, "high": 0}
    for log in logs:
        risk_levels[log.risk_level] = risk_levels.get(log.risk_level, 0) + 1

    # Route breakdown
    routes = {}
    for log in logs:
        if log.route not in routes:
            routes[log.route] = {"total": 0, "blocked": 0, "redacted": 0, "allowed": 0}
        routes[log.route]["total"] += 1
        routes[log.route][log.decision.lower()] += 1

    return {
        "summary": {
            "total_requests": total,
            "blocked_requests": blocked,
            "redacted_requests": redacted,
            "allowed_requests": allowed,
            "block_rate": blocked / total if total > 0 else 0,
            "redaction_rate": redacted / total if total > 0 else 0,
        },
        "risk_levels": risk_levels,
        "routes": routes,
    }
