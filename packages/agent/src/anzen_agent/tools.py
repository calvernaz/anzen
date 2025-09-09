"""
External API Tools for Anzen Agent

Tools for accessing Wikipedia and Weather APIs.
"""

import logging
from typing import Optional

import httpx

# Try to import wikipedia, handle if not available
try:
    import wikipedia

    WIKIPEDIA_AVAILABLE = True
except Exception as e:
    WIKIPEDIA_AVAILABLE = False

    # Mock wikipedia module
    class MockWikipedia:
        @staticmethod
        def set_lang(lang):
            pass

        @staticmethod
        def search(query, results=3):
            return ["Mock result"]

        @staticmethod
        def summary(title, sentences=3):
            return "Mock Wikipedia summary"

        class DisambiguationError(Exception):
            def __init__(self):
                self.options = ["Mock option"]

        class PageError(Exception):
            pass

    wikipedia = MockWikipedia()

logger = logging.getLogger(__name__)


class WikipediaTool:
    """Tool for searching Wikipedia."""

    def __init__(self):
        # Set Wikipedia to English and limit results
        wikipedia.set_lang("en")

    async def search(self, query: str, max_length: int = 500) -> str:
        """
        Search Wikipedia for information.

        Args:
            query: Search query
            max_length: Maximum length of returned text

        Returns:
            Wikipedia summary or error message
        """
        try:
            logger.info(f"Searching Wikipedia for: {query}")

            # Search for pages
            search_results = wikipedia.search(query, results=3)

            if not search_results:
                return f"No Wikipedia results found for '{query}'"

            # Try to get summary of the first result
            try:
                summary = wikipedia.summary(search_results[0], sentences=3)

                # Truncate if too long
                if len(summary) > max_length:
                    summary = summary[:max_length] + "..."

                logger.info(f"Wikipedia search successful: {len(summary)} characters")
                return summary

            except wikipedia.DisambiguationError as e:
                # Try the first option from disambiguation
                try:
                    summary = wikipedia.summary(e.options[0], sentences=3)
                    if len(summary) > max_length:
                        summary = summary[:max_length] + "..."
                    return summary
                except:
                    return f"Found multiple results for '{query}'. Please be more specific."

            except wikipedia.PageError:
                return f"No Wikipedia page found for '{query}'"

        except Exception as e:
            logger.error(f"Wikipedia search failed: {e}")
            return f"Wikipedia search failed: {str(e)}"


class WeatherTool:
    """Tool for getting weather information."""

    def __init__(self):
        self.client = httpx.AsyncClient(timeout=10.0)
        # Using a free weather API (OpenWeatherMap alternative)
        self.base_url = "https://api.open-meteo.com/v1/forecast"

    async def get_weather(self, location: str) -> str:
        """
        Get current weather for a location.

        Args:
            location: Location name (city, country)

        Returns:
            Weather description or error message
        """
        try:
            logger.info(f"Getting weather for: {location}")

            # First, get coordinates for the location using geocoding
            geocoding_url = "https://geocoding-api.open-meteo.com/v1/search"
            geocoding_params = {
                "name": location,
                "count": 1,
                "language": "en",
                "format": "json",
            }

            geocoding_response = await self.client.get(
                geocoding_url, params=geocoding_params
            )
            geocoding_response.raise_for_status()
            geocoding_data = geocoding_response.json()

            if not geocoding_data.get("results"):
                return f"Location '{location}' not found"

            # Get coordinates
            location_data = geocoding_data["results"][0]
            lat = location_data["latitude"]
            lon = location_data["longitude"]
            location_name = location_data["name"]
            country = location_data.get("country", "")

            # Get weather data
            weather_params = {
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,relative_humidity_2m,weather_code,wind_speed_10m",
                "timezone": "auto",
            }

            weather_response = await self.client.get(
                self.base_url, params=weather_params
            )
            weather_response.raise_for_status()
            weather_data = weather_response.json()

            # Extract current weather
            current = weather_data["current"]
            temperature = current["temperature_2m"]
            humidity = current["relative_humidity_2m"]
            wind_speed = current["wind_speed_10m"]
            weather_code = current["weather_code"]

            # Convert weather code to description
            weather_description = self._weather_code_to_description(weather_code)

            result = f"Current weather in {location_name}"
            if country:
                result += f", {country}"
            result += f": {weather_description}, {temperature}°C, {humidity}% humidity, wind {wind_speed} km/h"

            logger.info(f"Weather lookup successful for {location}")
            return result

        except httpx.HTTPError as e:
            logger.error(f"HTTP error during weather lookup: {e}")
            return f"Weather service unavailable for '{location}'"
        except Exception as e:
            logger.error(f"Weather lookup failed: {e}")
            return f"Weather lookup failed for '{location}': {str(e)}"

    def _weather_code_to_description(self, code: int) -> str:
        """Convert WMO weather code to description."""
        weather_codes = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Depositing rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Slight rain",
            63: "Moderate rain",
            65: "Heavy rain",
            71: "Slight snow",
            73: "Moderate snow",
            75: "Heavy snow",
            77: "Snow grains",
            80: "Slight rain showers",
            81: "Moderate rain showers",
            82: "Violent rain showers",
            85: "Slight snow showers",
            86: "Heavy snow showers",
            95: "Thunderstorm",
            96: "Thunderstorm with slight hail",
            99: "Thunderstorm with heavy hail",
        }
        return weather_codes.get(code, f"Unknown weather (code: {code})")

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
