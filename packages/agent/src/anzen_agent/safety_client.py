"""
Safety Client for Anzen Gateway Integration

HTTP client for communicating with the Anzen Safety Gateway.
"""

import logging
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)


class SafetyClient:
    """Client for communicating with the Anzen Safety Gateway."""

    def __init__(self, gateway_url: str, api_key: Optional[str] = None):
        self.gateway_url = gateway_url.rstrip("/")
        self.api_key = api_key

        # Set up headers with API key if provided
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        self.client = httpx.AsyncClient(timeout=30.0, headers=headers)

    async def check_input(
        self, text: str, route: str = "private:agent", language: str = "en"
    ) -> Dict[str, Any]:
        """
        Check input text for PII and safety issues.

        Args:
            text: Input text to check
            route: Route classification (e.g., "private:agent")
            language: Language code

        Returns:
            Safety check result with decision, entities, safe_text, etc.
        """
        try:
            url = f"{self.gateway_url}/v1/anzen/check/input"
            payload = {"text": text, "route": route, "language": language}

            logger.debug(f"Sending input safety check to {url}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Input safety check result: {result['decision']}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during input safety check: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during input safety check: {e}")
            raise

    async def check_output(
        self, text: str, route: str = "private:agent", language: str = "en"
    ) -> Dict[str, Any]:
        """
        Check output text for PII and apply redaction.

        Args:
            text: Output text to check
            route: Route classification (e.g., "private:agent")
            language: Language code

        Returns:
            Safety check result with decision, entities, safe_text, etc.
        """
        try:
            url = f"{self.gateway_url}/v1/anzen/check/output"
            payload = {"text": text, "route": route, "language": language}

            logger.debug(f"Sending output safety check to {url}")
            response = await self.client.post(url, json=payload)
            response.raise_for_status()

            result = response.json()
            logger.debug(f"Output safety check result: {result['decision']}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during output safety check: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error during output safety check: {e}")
            raise

    async def health_check(self) -> bool:
        """
        Check if the safety gateway is healthy.

        Returns:
            True if gateway is healthy, False otherwise
        """
        try:
            url = f"{self.gateway_url}/health"
            response = await self.client.get(url)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Gateway health check failed: {e}")
            return False

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
