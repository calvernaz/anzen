#!/usr/bin/env python3
"""
Database initialization script for Anzen Gateway

Creates initial database schema and seed data.
"""

import asyncio
import sys
from pathlib import Path

# Add the src directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import logging

from anzen_gateway.auth import AuthManager, create_api_key, create_user
from anzen_gateway.config import get_settings
from anzen_gateway.database import (DatabaseManager, Organization,
                                    PolicyTemplate, User)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_default_organization(db_manager: DatabaseManager) -> Organization:
    """Create the default organization."""
    session = db_manager.get_session()

    try:
        # Check if organization already exists
        org = session.query(Organization).filter(Organization.slug == "default").first()
        if org:
            logger.info("Default organization already exists")
            return org

        # Create default organization
        org = Organization(
            name="Default Organization",
            slug="default",
            settings={
                "default_route": "private:general",
                "max_api_keys_per_user": 10,
                "retention_days": 90,
            },
        )

        session.add(org)
        session.commit()
        session.refresh(org)

        logger.info(f"Created default organization: {org.name}")
        return org

    finally:
        session.close()


def create_admin_user(db_manager: DatabaseManager, organization: Organization) -> User:
    """Create the default admin user."""
    session = db_manager.get_session()

    try:
        # Check if admin user already exists
        admin = session.query(User).filter(User.email == "admin@anzen.dev").first()
        if admin:
            logger.info("Admin user already exists")
            return admin

        # Create admin user
        admin = create_user(
            email="admin@anzen.dev",
            name="Admin User",
            password="admin123",  # Change this in production!
            organization_id=str(organization.id),
            db=session,
            is_admin=True,
        )

        logger.info(f"Created admin user: {admin.email}")
        logger.warning(
            "⚠️  Default admin password is 'admin123' - CHANGE THIS IN PRODUCTION!"
        )

        return admin

    finally:
        session.close()


def create_default_api_key(
    db_manager: DatabaseManager, user: User, organization: Organization
) -> str:
    """Create a default API key for testing."""
    session = db_manager.get_session()

    try:
        # Create API key
        full_key, api_key_record = create_api_key(
            name="Default API Key",
            user_id=str(user.id),
            organization_id=str(organization.id),
            db=session,
            expires_days=365,  # 1 year expiration
        )

        logger.info(f"Created default API key: {api_key_record.key_prefix}")
        logger.info(f"🔑 API Key: {full_key}")
        logger.warning("⚠️  Save this API key - it won't be shown again!")

        return full_key

    finally:
        session.close()


def create_policy_templates(db_manager: DatabaseManager):
    """Create default policy templates."""
    session = db_manager.get_session()

    try:
        templates = [
            {
                "name": "Public Chatbot",
                "description": "Strict policy for public-facing chatbots",
                "route_pattern": "public:*",
                "policy_config": {
                    "block_entities": [
                        "CREDIT_CARD",
                        "US_SSN",
                        "US_PASSPORT",
                        "IBAN_CODE",
                    ],
                    "redact_entities": ["EMAIL_ADDRESS", "PHONE_NUMBER"],
                    "risk_threshold": 0.8,
                    "allow_override": False,
                },
            },
            {
                "name": "Support Desk",
                "description": "Moderate policy for customer support",
                "route_pattern": "private:support",
                "policy_config": {
                    "block_entities": ["CREDIT_CARD", "US_SSN", "US_PASSPORT"],
                    "redact_entities": [
                        "EMAIL_ADDRESS",
                        "PHONE_NUMBER",
                        "PERSON",
                        "IBAN_CODE",
                    ],
                    "risk_threshold": 0.9,
                    "allow_override": True,
                },
            },
            {
                "name": "Internal Operations",
                "description": "Permissive policy for internal use",
                "route_pattern": "internal:*",
                "policy_config": {
                    "block_entities": ["CREDIT_CARD", "US_SSN"],
                    "redact_entities": [],
                    "risk_threshold": 0.95,
                    "allow_override": True,
                },
            },
        ]

        for template_data in templates:
            # Check if template already exists
            existing = (
                session.query(PolicyTemplate)
                .filter(PolicyTemplate.name == template_data["name"])
                .first()
            )

            if existing:
                logger.info(f"Policy template '{template_data['name']}' already exists")
                continue

            template = PolicyTemplate(
                name=template_data["name"],
                description=template_data["description"],
                route_pattern=template_data["route_pattern"],
                policy_config=template_data["policy_config"],
                is_builtin=True,
            )

            session.add(template)
            logger.info(f"Created policy template: {template.name}")

        session.commit()

    finally:
        session.close()


def main():
    """Initialize the database with default data."""
    logger.info("🚀 Initializing Anzen Gateway Database")

    # Get settings
    settings = get_settings()
    logger.info(f"Database URL: {settings.database_url}")

    # Create database manager
    db_manager = DatabaseManager(settings.database_url)

    try:
        # Create tables
        logger.info("📋 Creating database tables...")
        db_manager.create_tables()

        # Create default organization
        logger.info("🏢 Creating default organization...")
        organization = create_default_organization(db_manager)

        # Create admin user
        logger.info("👤 Creating admin user...")
        admin_user = create_admin_user(db_manager, organization)

        # Create default API key
        logger.info("🔑 Creating default API key...")
        api_key = create_default_api_key(db_manager, admin_user, organization)

        # Create policy templates
        logger.info("📜 Creating policy templates...")
        create_policy_templates(db_manager)

        logger.info("✅ Database initialization completed successfully!")

        print("\n" + "=" * 60)
        print("🎉 Anzen Gateway Database Initialized!")
        print("=" * 60)
        print(f"Organization: {organization.name} ({organization.slug})")
        print(f"Admin Email: {admin_user.email}")
        print(f"Admin Password: admin123 (CHANGE THIS!)")
        print(f"API Key: {api_key}")
        print("\n📚 Next Steps:")
        print("1. Change the admin password")
        print("2. Create additional users and API keys")
        print("3. Start the gateway: uv run anzen-gateway")
        print("4. Test the API with the provided API key")
        print("=" * 60)

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        sys.exit(1)

    finally:
        db_manager.close()


if __name__ == "__main__":
    main()
