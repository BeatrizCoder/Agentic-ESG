"""Weather check tool using the OpenWeatherMap API."""

from crewai.tools import BaseTool
from pydantic import BaseModel, Field
import urllib.request
import urllib.error
import urllib.parse
import json
import time
import logging
import os

logger = logging.getLogger(__name__)


class WeatherCheckInput(BaseModel):
    city: str = Field(
        description="City name to check weather conditions. "
                    "Examples: 'São Paulo', 'Rio de Janeiro', "
                    "'Curitiba'. Used to check if weather may "
                    "be causing delivery delays."
    )


class WeatherCheckTool(BaseTool):
    name: str = "Weather Check Tool"
    description: str = (
        "Checks current weather conditions in a Brazilian city "
        "to determine if adverse weather may be causing delivery "
        "delays. Returns temperature, conditions, and whether "
        "weather could affect logistics. "
        "Input: city name. Output: weather data or error."
    )
    args_schema: type[BaseModel] = WeatherCheckInput

    timeout_seconds: int = 5
    max_retries: int = 2
    retry_delay: float = 1.0

    # Weather codes that indicate adverse conditions
    adverse_weather_codes: list = [
        200, 201, 202, 210, 211, 212, 221, 230, 231, 232,  # thunderstorm
        300, 301, 302, 310, 311, 312, 313, 314, 321,        # drizzle
        500, 501, 502, 503, 504, 511, 520, 521, 522, 531,   # rain
        600, 601, 602, 611, 612, 613, 615, 616, 620, 621,   # snow
        762, 771, 781,                                        # volcanic, squall, tornado
    ]

    def _get_api_key(self) -> str:
        key = os.environ.get("OPENWEATHER_API_KEY", "")
        if not key:
            raise ValueError("OPENWEATHER_API_KEY not set in environment")
        return key

    def _is_adverse(self, weather_id: int) -> bool:
        return weather_id in self.adverse_weather_codes

    def _fetch_with_retry(self, url: str) -> dict:
        last_error = None

        for attempt in range(self.max_retries + 1):
            try:
                logger.info(
                    "WeatherCheckTool: attempt %d/%d",
                    attempt + 1, self.max_retries + 1
                )
                start = time.time()

                req = urllib.request.Request(
                    url,
                    headers={"Accept": "application/json"}
                )

                with urllib.request.urlopen(
                    req, timeout=self.timeout_seconds
                ) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    latency_ms = round((time.time() - start) * 1000, 2)
                    logger.info(
                        "WeatherCheckTool: success latency=%sms", latency_ms
                    )
                    return data

            except urllib.error.HTTPError as e:
                if e.code == 401:
                    raise ValueError("Invalid OpenWeather API key")
                elif e.code == 404:
                    raise LookupError("City not found")
                elif e.code == 429:
                    last_error = "Rate limit exceeded (429)"
                    logger.warning(
                        "WeatherCheckTool: rate limit hit, waiting before retry..."
                    )
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay * 2)
                else:
                    last_error = f"HTTP {e.code}: {e.reason}"
                    if attempt < self.max_retries:
                        time.sleep(self.retry_delay)

            except urllib.error.URLError as e:
                last_error = f"Network error: {e.reason}"
                logger.warning(
                    "WeatherCheckTool: attempt %d failed: %s",
                    attempt + 1, last_error
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

            except TimeoutError:
                last_error = f"Timeout after {self.timeout_seconds}s"
                logger.warning(
                    "WeatherCheckTool: timeout on attempt %d", attempt + 1
                )
                if attempt < self.max_retries:
                    time.sleep(self.retry_delay)

        raise ConnectionError(last_error)

    def _run(self, city: str) -> dict:
        start_time = time.time()

        try:
            api_key = self._get_api_key()
        except ValueError as e:
            logger.error("WeatherCheckTool: %s", e)
            return {
                "available": False,
                "city": city,
                "error": str(e),
                "error_type": "config_error",
                "fallback": "Weather check unavailable — API key not configured.",
                "adverse_conditions": False,
                "latency_ms": 0,
            }

        url = (
            f"https://api.openweathermap.org/data/2.5/weather"
            f"?q={urllib.parse.quote(city)},BR"
            f"&appid={api_key}&units=metric&lang=pt_br"
        )

        try:
            data = self._fetch_with_retry(url)
            latency_ms = round((time.time() - start_time) * 1000, 2)

            weather_id = data["weather"][0]["id"]
            weather_desc = data["weather"][0]["description"]
            temp = data["main"]["temp"]
            feels_like = data["main"]["feels_like"]
            humidity = data["main"]["humidity"]
            adverse = self._is_adverse(weather_id)

            result = {
                "available": True,
                "city": data.get("name", city),
                "country": data.get("sys", {}).get("country", "BR"),
                "temperature_c": round(temp, 1),
                "feels_like_c": round(feels_like, 1),
                "humidity_pct": humidity,
                "conditions": weather_desc,
                "weather_id": weather_id,
                "adverse_conditions": adverse,
                "delivery_impact": (
                    "Adverse weather conditions detected — "
                    "deliveries may be delayed in this region."
                    if adverse else
                    "Weather conditions are normal — "
                    "no weather-related delays expected."
                ),
                "source": "openweathermap",
                "latency_ms": latency_ms,
            }

            logger.info(
                "WeatherCheckTool: %s → %s°C, %s, adverse=%s",
                city, temp, weather_desc, adverse
            )
            return result

        except LookupError:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            return {
                "available": False,
                "city": city,
                "error": f"City '{city}' not found.",
                "error_type": "city_not_found",
                "adverse_conditions": False,
                "fallback": "Could not check weather — proceeding without weather data.",
                "latency_ms": latency_ms,
            }

        except ValueError as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.error("WeatherCheckTool: auth error: %s", e)
            return {
                "available": False,
                "city": city,
                "error": str(e),
                "error_type": "auth_error",
                "adverse_conditions": False,
                "fallback": "Weather check unavailable — invalid API key.",
                "latency_ms": latency_ms,
            }

        except ConnectionError as e:
            latency_ms = round((time.time() - start_time) * 1000, 2)
            logger.error(
                "WeatherCheckTool: failed after retries: %s", e
            )
            return {
                "available": False,
                "city": city,
                "error": str(e),
                "error_type": "api_unavailable",
                "adverse_conditions": False,
                "fallback": "Weather check temporarily unavailable — proceeding without weather data.",
                "latency_ms": latency_ms,
            }
