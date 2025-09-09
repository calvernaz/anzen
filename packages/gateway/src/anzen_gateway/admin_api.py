"""
Admin API endpoints for Anzen Gateway

User management, API key management, and compliance reporting.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr
from sqlalchemy.orm import Session

from .audit import AuditLogger
from .auth import (AuthManager, authenticate_user, create_api_key, create_user,
                   get_current_active_user)
from .database import (APIKey, AuditLog, Organization, User,
                       get_database_session)

logger = logging.getLogger(__name__)


# Request/Response models
class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    user: dict


class CreateUserRequest(BaseModel):
    email: EmailStr
    name: str
    password: str
    is_admin: bool = False


class CreateAPIKeyRequest(BaseModel):
    name: str
    expires_days: Optional[int] = None


class APIKeyResponse(BaseModel):
    id: str
    name: str
    key_prefix: str
    api_key: Optional[str] = None  # Only returned on creation
    created_at: datetime
    expires_at: Optional[datetime]
    last_used: Optional[datetime]
    usage_count: int
    is_active: bool


class ComplianceReportRequest(BaseModel):
    start_date: datetime
    end_date: datetime
    route_filter: Optional[str] = None


class AdminAPI:
    """Admin API for user and organization management."""

    def __init__(self):
        self.router = APIRouter(prefix="/admin", tags=["admin"])
        self._setup_routes()

    def _setup_routes(self):
        """Setup admin API routes."""

        @self.router.post("/login", response_model=LoginResponse)
        async def login(
            request: LoginRequest, db: Session = Depends(get_database_session)
        ):
            """Authenticate user and return JWT token."""
            user = authenticate_user(request.email, request.password, db)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Incorrect email or password",
                )

            # Update last login
            user.last_login = datetime.now(timezone.utc)
            db.commit()

            # Create access token
            access_token = AuthManager.create_access_token(data={"sub": str(user.id)})

            return LoginResponse(
                access_token=access_token,
                token_type="bearer",
                user={
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "is_admin": user.is_admin,
                    "organization": user.organization.name,
                },
            )

        @self.router.post("/users", response_model=dict)
        async def create_new_user(
            request: CreateUserRequest,
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Create a new user (admin only)."""
            if not current_user.is_admin:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Admin access required",
                )

            try:
                user = create_user(
                    email=request.email,
                    name=request.name,
                    password=request.password,
                    organization_id=str(current_user.organization_id),
                    db=db,
                    is_admin=request.is_admin,
                )

                return {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "is_admin": user.is_admin,
                    "created_at": user.created_at.isoformat(),
                }

            except ValueError as e:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
                )

        @self.router.get("/users", response_model=List[dict])
        async def list_users(
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """List users in the organization."""
            users = (
                db.query(User)
                .filter(User.organization_id == current_user.organization_id)
                .all()
            )

            return [
                {
                    "id": str(user.id),
                    "email": user.email,
                    "name": user.name,
                    "is_admin": user.is_admin,
                    "is_active": user.is_active,
                    "created_at": user.created_at.isoformat(),
                    "last_login": (
                        user.last_login.isoformat() if user.last_login else None
                    ),
                }
                for user in users
            ]

        @self.router.post("/api-keys", response_model=APIKeyResponse)
        async def create_new_api_key(
            request: CreateAPIKeyRequest,
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Create a new API key."""
            full_key, api_key_record = create_api_key(
                name=request.name,
                user_id=str(current_user.id),
                organization_id=str(current_user.organization_id),
                db=db,
                expires_days=request.expires_days,
            )

            return APIKeyResponse(
                id=str(api_key_record.id),
                name=api_key_record.name,
                key_prefix=api_key_record.key_prefix,
                api_key=full_key,  # Only returned on creation
                created_at=api_key_record.created_at,
                expires_at=api_key_record.expires_at,
                last_used=api_key_record.last_used,
                usage_count=api_key_record.usage_count,
                is_active=api_key_record.is_active,
            )

        @self.router.get("/api-keys", response_model=List[APIKeyResponse])
        async def list_api_keys(
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """List API keys for the current user."""
            api_keys = db.query(APIKey).filter(APIKey.user_id == current_user.id).all()

            return [
                APIKeyResponse(
                    id=str(key.id),
                    name=key.name,
                    key_prefix=key.key_prefix,
                    created_at=key.created_at,
                    expires_at=key.expires_at,
                    last_used=key.last_used,
                    usage_count=key.usage_count,
                    is_active=key.is_active,
                )
                for key in api_keys
            ]

        @self.router.delete("/api-keys/{key_id}")
        async def delete_api_key(
            key_id: str,
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Delete an API key."""
            api_key = (
                db.query(APIKey)
                .filter(APIKey.id == key_id, APIKey.user_id == current_user.id)
                .first()
            )

            if not api_key:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND, detail="API key not found"
                )

            api_key.is_active = False
            db.commit()

            return {"message": "API key deleted successfully"}

        @self.router.post("/reports/compliance")
        async def generate_compliance_report(
            request: ComplianceReportRequest,
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Generate a compliance report."""
            audit_logger = AuditLogger(db)

            report = audit_logger.get_compliance_report(
                organization_id=str(current_user.organization_id),
                start_date=request.start_date,
                end_date=request.end_date,
                route_filter=request.route_filter,
            )

            return report

        @self.router.get("/logs/recent")
        async def get_recent_logs(
            limit: int = 100,
            route_filter: Optional[str] = None,
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Get recent audit logs."""
            audit_logger = AuditLogger(db)

            logs = audit_logger.get_recent_logs(
                organization_id=str(current_user.organization_id),
                limit=limit,
                route_filter=route_filter,
            )

            return {"logs": logs, "total": len(logs)}

        @self.router.get("/dashboard/stats")
        async def get_dashboard_stats(
            current_user: User = Depends(get_current_active_user),
            db: Session = Depends(get_database_session),
        ):
            """Get dashboard statistics."""
            # Get stats for the last 24 hours
            end_date = datetime.now(timezone.utc)
            start_date = end_date - timedelta(days=1)

            audit_logger = AuditLogger(db)
            report = audit_logger.get_compliance_report(
                organization_id=str(current_user.organization_id),
                start_date=start_date,
                end_date=end_date,
            )

            # Get user count
            user_count = (
                db.query(User)
                .filter(
                    User.organization_id == current_user.organization_id,
                    User.is_active == True,
                )
                .count()
            )

            # Get API key count
            api_key_count = (
                db.query(APIKey)
                .filter(
                    APIKey.organization_id == current_user.organization_id,
                    APIKey.is_active == True,
                )
                .count()
            )

            return {
                "last_24h": report["summary"],
                "user_count": user_count,
                "api_key_count": api_key_count,
                "organization": {
                    "name": current_user.organization.name,
                    "slug": current_user.organization.slug,
                },
            }
