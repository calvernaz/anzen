"""
Authentication and authorization for Anzen Gateway

JWT tokens, API key validation, and user management.
"""

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from .database import APIKey, Organization, User, get_database_session

logger = logging.getLogger(__name__)

# Security configuration
SECRET_KEY = "anzen-secret-key-change-in-production"  # TODO: Use environment variable
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
security = HTTPBearer()


class AuthenticationError(Exception):
    """Authentication error."""

    pass


class AuthManager:
    """Authentication and authorization manager."""

    @staticmethod
    def verify_password(plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash."""
        return pwd_context.verify(plain_password, hashed_password)

    @staticmethod
    def get_password_hash(password: str) -> str:
        """Hash a password."""
        return pwd_context.hash(password)

    @staticmethod
    def create_access_token(
        data: dict, expires_delta: Optional[timedelta] = None
    ) -> str:
        """Create a JWT access token."""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(minutes=15)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    @staticmethod
    def verify_token(token: str) -> dict:
        """Verify and decode a JWT token."""
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            raise AuthenticationError("Invalid token")

    @staticmethod
    def generate_api_key() -> Tuple[str, str, str]:
        """
        Generate a new API key.

        Returns:
            Tuple of (full_key, key_hash, key_prefix)
        """
        # Generate a secure random key
        key = f"ak_{secrets.token_urlsafe(32)}"

        # Create hash for storage
        key_hash = hashlib.sha256(key.encode()).hexdigest()

        # Create prefix for display
        key_prefix = key[:12] + "..."

        return key, key_hash, key_prefix

    @staticmethod
    def hash_api_key(api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()


def authenticate_user(email: str, password: str, db: Session) -> Optional[User]:
    """Authenticate a user with email and password."""
    user = db.query(User).filter(User.email == email).first()
    if not user:
        return None
    if not AuthManager.verify_password(password, user.hashed_password):
        return None
    return user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_database_session),
) -> User:
    """Get current user from JWT token."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = AuthManager.verify_token(credentials.credentials)
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except AuthenticationError:
        raise credentials_exception

    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception

    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    """Get current active user."""
    if not current_user.is_active:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


def validate_api_key(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_database_session),
) -> Tuple[APIKey, User, Organization]:
    """
    Validate API key and return associated key, user, and organization.

    Returns:
        Tuple of (api_key, user, organization)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Extract API key from Authorization header
    api_key = credentials.credentials
    if not api_key.startswith("ak_"):
        raise credentials_exception

    # Hash the provided key
    key_hash = AuthManager.hash_api_key(api_key)

    # Look up the API key
    api_key_record = (
        db.query(APIKey)
        .filter(APIKey.key_hash == key_hash, APIKey.is_active == True)
        .first()
    )

    if not api_key_record:
        raise credentials_exception

    # Check if key is expired
    if api_key_record.expires_at and api_key_record.expires_at < datetime.now(
        timezone.utc
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="API key expired"
        )

    # Update last used timestamp and usage count
    api_key_record.last_used = datetime.now(timezone.utc)
    api_key_record.usage_count += 1
    db.commit()

    # Get associated user and organization
    user = api_key_record.user
    organization = api_key_record.organization

    if not user.is_active or not organization.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User or organization inactive",
        )

    return api_key_record, user, organization


def create_user(
    email: str,
    name: str,
    password: str,
    organization_id: str,
    db: Session,
    is_admin: bool = False,
) -> User:
    """Create a new user."""
    # Check if user already exists
    existing_user = db.query(User).filter(User.email == email).first()
    if existing_user:
        raise ValueError("User with this email already exists")

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

    logger.info(f"Created user: {email}")
    return user


def create_api_key(
    name: str,
    user_id: str,
    organization_id: str,
    db: Session,
    expires_days: Optional[int] = None,
) -> Tuple[str, APIKey]:
    """
    Create a new API key for a user.

    Returns:
        Tuple of (full_api_key, api_key_record)
    """
    # Generate API key
    full_key, key_hash, key_prefix = AuthManager.generate_api_key()

    # Calculate expiration
    expires_at = None
    if expires_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=expires_days)

    # Create API key record
    api_key = APIKey(
        name=name,
        key_hash=key_hash,
        key_prefix=key_prefix,
        user_id=user_id,
        organization_id=organization_id,
        expires_at=expires_at,
    )

    db.add(api_key)
    db.commit()
    db.refresh(api_key)

    logger.info(f"Created API key: {name} for user {user_id}")
    return full_key, api_key
