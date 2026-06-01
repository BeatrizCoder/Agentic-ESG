"""Weather API Tool for external weather data integration."""

import time
import logging
import random
from typing import Dict, Any
from . import BaseSupportTool
from pydantic import BaseModel, Field

from src.aamad.config import (
    INTEGRATION_CONFIG,
    ENABLE_MOCK_INTEGRATIONS
)

logger = logging.getLogger(__name__)


class WeatherRequest(BaseModel):
    """Request model for weather API calls."""
    location: str = Field(..., description="City name or coordinates (lat,lng)")
    units: str = Field(default="metric", description="Temperature units (metric/imperial)")
    include_forecast: bool = Field(default=False, description="Include 5-day forecast")


class WeatherTool(BaseSupportTool):
    """Weather API tool for retrieving weather data."""

    name: str = "Weather Tool"
    description: str = "Tool for retrieving current weather and forecast data"

    def __init__(self):
        super().__init__()
        self.api_name = "weather_api"
        self.retry_count = INTEGRATION_CONFIG["retry_count"]
        self.timeout_seconds = INTEGRATION_CONFIG["timeout_seconds"]
        self.rate_limit_per_minute = INTEGRATION_CONFIG["rate_limit_per_minute"]

    def _run(self, request: WeatherRequest) -> Dict[str, Any]:
        """Execute weather API call (mock implementation)."""
        start_time = time.time()

        try:
            # Log integration attempt
            logger.info(f"Integration attempt: {self.api_name}, mode=mock, location={request.location}")

            if not ENABLE_MOCK_INTEGRATIONS:
                return {
                    "success": False,
                    "error": "Mock integrations disabled",
                    "latency": time.time() - start_time,
                    "status": "disabled"
                }

            # Simulate weather API call
            time.sleep(0.2)  # Simulate network latency

            # Mock weather data
            conditions = ["sunny", "cloudy", "rainy", "snowy", "windy", "foggy"]
            current_weather = {
                "location": request.location,
                "temperature": round(random.uniform(15, 30), 1) if request.units == "metric" else round(random.uniform(59, 86), 1),
                "condition": random.choice(conditions),
                "humidity": random.randint(40, 90),
                "wind_speed": round(random.uniform(5, 25), 1),
                "units": request.units,
                "timestamp": "2024-01-01T12:00:00Z"
            }

            forecast_data = []
            if request.include_forecast:
                for i in range(5):
                    forecast_data.append({
                        "date": f"2024-01-{i+2:02d}",
                        "temperature_max": round(random.uniform(20, 35), 1),
                        "temperature_min": round(random.uniform(10, 20), 1),
                        "condition": random.choice(conditions),
                        "precipitation_chance": random.randint(0, 100)
                    })

            response_data = {
                "current": current_weather,
                "forecast": forecast_data if request.include_forecast else None
            }

            latency = time.time() - start_time

            # Log successful integration
            logger.info(f"Integration success: {self.api_name}, mode=mock, latency={latency:.2f}s, status=200")

            return {
                "success": True,
                "data": response_data,
                "latency": latency,
                "cached": False,
                "retries": 0,
                "api_used": "mock_weather_api"
            }

        except Exception as e:
            latency = time.time() - start_time
            logger.error(f"Integration error: {self.api_name}, mode=mock, latency={latency:.2f}s, error={str(e)}")

            return {
                "success": False,
                "error": str(e),
                "latency": latency,
                "status": "error"
            }

    async def _arun(self, request: WeatherRequest) -> Dict[str, Any]:
        """Async version of weather API call."""
        import asyncio
        # Simulate async operation
        await asyncio.sleep(0.1)
        return self._run(request)