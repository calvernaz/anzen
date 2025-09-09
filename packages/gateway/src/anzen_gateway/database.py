"""
Database models and connection for Anzen Gateway

SQLAlchemy models for users, audit logs, API keys, and policies.
"""

import uuid
from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import (JSON, Boolean, Column, DateTime, Float, ForeignKey,
                        Integer, String, Text, create_engine)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, relationship, sessionmaker

# Use String for UUIDs to support SQLite
UUID_TYPE = String(36)
import logging

logger = logging.getLogger(__name__)

Base = declarative_base()


class Organization(Base):
    """Organization/tenant model."""

    __tablename__ = "organizations"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    slug = Column(String(100), unique=True, nullable=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Settings
    settings = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)

    # Relationships
    users = relationship("User", back_populates="organization")
    api_keys = relationship("APIKey", back_populates="organization")
    audit_logs = relationship("AuditLog", back_populates="organization")


class User(Base):
    """User model."""

    __tablename__ = "users"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String(255), unique=True, nullable=False)
    name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)

    # Organization relationship
    organization_id = Column(UUID_TYPE, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="users")

    # User properties
    is_active = Column(Boolean, default=True)
    is_admin = Column(Boolean, default=False)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )
    last_login = Column(DateTime(timezone=True), nullable=True)

    # Relationships
    api_keys = relationship("APIKey", back_populates="user")


class APIKey(Base):
    """API key model for authentication."""

    __tablename__ = "api_keys"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    key_hash = Column(String(255), unique=True, nullable=False)  # Hashed API key
    key_prefix = Column(String(20), nullable=False)  # First few chars for display

    # Relationships
    user_id = Column(UUID_TYPE, ForeignKey("users.id"), nullable=False)
    user = relationship("User", back_populates="api_keys")
    organization_id = Column(UUID_TYPE, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="api_keys")

    # Key properties
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    expires_at = Column(DateTime(timezone=True), nullable=True)
    last_used = Column(DateTime(timezone=True), nullable=True)

    # Usage tracking
    usage_count = Column(Integer, default=0)
    rate_limit = Column(Integer, default=1000)  # Requests per hour


class AuditLog(Base):
    """Audit log model for compliance tracking."""

    __tablename__ = "audit_logs"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))

    # Request identification
    trace_id = Column(String(100), nullable=False, index=True)
    session_id = Column(String(100), nullable=True)

    # Organization relationship
    organization_id = Column(UUID_TYPE, ForeignKey("organizations.id"), nullable=False)
    organization = relationship("Organization", back_populates="audit_logs")

    # Request details
    route = Column(String(100), nullable=False)
    method = Column(String(10), nullable=False)  # input, output

    # PII detection results
    entities_detected = Column(JSON, default=list)  # List of entity types
    entity_count = Column(Integer, default=0)
    risk_level = Column(String(20), nullable=False)  # low, medium, high

    # Policy decision
    decision = Column(String(20), nullable=False)  # ALLOW, BLOCK, REDACT
    policy_applied = Column(String(100), nullable=True)

    # Text analysis (hashed for privacy)
    input_hash = Column(String(64), nullable=True)  # SHA-256 hash of input
    output_hash = Column(String(64), nullable=True)  # SHA-256 hash of output
    text_length = Column(Integer, nullable=False)

    # Timing and performance
    processing_time_ms = Column(Float, nullable=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    # Additional metadata
    extra_metadata = Column(JSON, default=dict)


class PolicyTemplate(Base):
    """Policy template model."""

    __tablename__ = "policy_templates"

    id = Column(UUID_TYPE, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Template configuration
    route_pattern = Column(
        String(100), nullable=False
    )  # e.g., "public:*", "private:support"
    policy_config = Column(JSON, nullable=False)  # Policy rules

    # Template properties
    is_builtin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class DatabaseManager:
    """Database connection and session management."""

    def __init__(self, database_url: str):
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


# Dependency for FastAPI
def get_database_session():
    """FastAPI dependency to get database session."""
    from .config import get_settings

    settings = get_settings()

    # Create database manager if not exists
    if not hasattr(get_database_session, "_db_manager"):
        get_database_session._db_manager = DatabaseManager(settings.database_url)
        get_database_session._db_manager.create_tables()

    session = get_database_session._db_manager.get_session()
    try:
        yield session
    finally:
        session.close()
