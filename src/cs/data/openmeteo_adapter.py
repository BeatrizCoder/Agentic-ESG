"""Adapter for Open-Meteo — current forecast (16 days) and IPCC climate projections to 2050."""

import asyncio
import logging
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_FORECAST_URL    = "https://api.open-meteo.com/v1/forecast"
_PROJECTION_URL  = "https://climate-api.open-meteo.com/v1/climate"
_PROJECTION_MODEL = "EC_Earth3P_HR"
_FILL = -999.0


@dataclass
class ForecastRecord:
    date: str
    temp_max_c: float
    temp_min_c: float
    precip_mm: float


@dataclass
class ProjectionRecord:
    year: int
    temp_mean_c: float
    precip_total_mm: float


@dataclass
class OpenMeteoResult:
    latitude: float
    longitude: float
    forecast_records: list[ForecastRecord] = field(default_factory=list)
    projection_records: list[ProjectionRecord] = field(default_factory=list)
    forecast_url: str = ""
    projection_url: str = ""
    model: str = _PROJECTION_MODEL
    error: str = ""


async def fetch_openmeteo_data(latitude: float, longitude: float) -> OpenMeteoResult:
    """Fetch 16-day forecast and IPCC climate projections in parallel."""
    try:
        forecast_coro = _fetch_forecast(latitude, longitude)
        projection_coro = _fetch_projections(latitude, longitude, 2024, 2050)
        forecast, projection = await asyncio.gather(
            forecast_coro, projection_coro, return_exceptions=True
        )

        forecast_records, forecast_url = ([], "")
        if isinstance(forecast, Exception):
            logger.warning("OpenMeteo forecast fetch failed: %s", forecast)
        else:
            forecast_records, forecast_url = forecast

        projection_records, projection_url = ([], "")
        if isinstance(projection, Exception):
            logger.warning("OpenMeteo projection fetch failed: %s", projection)
        else:
            projection_records, projection_url = projection

        logger.info(
            "OpenMeteo: forecast=%d days  projections=%d years",
            len(forecast_records),
            len(projection_records),
        )
        return OpenMeteoResult(
            latitude=latitude,
            longitude=longitude,
            forecast_records=forecast_records,
            projection_records=projection_records,
            forecast_url=forecast_url,
            projection_url=projection_url,
        )

    except Exception as exc:
        logger.error("OpenMeteo fetch failed entirely: %s", exc)
        return OpenMeteoResult(latitude=latitude, longitude=longitude, error=str(exc))


async def _fetch_forecast(
    latitude: float, longitude: float
) -> tuple[list[ForecastRecord], str]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 16,
        "timezone": "auto",
    }
    async with httpx.AsyncClient(timeout=30.0) as client:
        req = client.build_request("GET", _FORECAST_URL, params=params)
        url = str(req.url)
        resp = await client.send(req)
        resp.raise_for_status()
        payload = resp.json()

    daily = payload.get("daily", {})
    dates   = daily.get("time", [])
    t_max   = daily.get("temperature_2m_max",  [])
    t_min   = daily.get("temperature_2m_min",  [])
    precip  = daily.get("precipitation_sum",   [])

    records = [
        ForecastRecord(
            date=dates[i],
            temp_max_c=float(t_max[i]) if t_max[i] is not None else 0.0,
            temp_min_c=float(t_min[i]) if t_min[i] is not None else 0.0,
            precip_mm=float(precip[i]) if precip[i] is not None else 0.0,
        )
        for i in range(len(dates))
    ]
    return records, url


async def fetch_projection_range(
    latitude: float,
    longitude: float,
    start_year: int = 2026,
    end_year: int = 2050,
) -> "OpenMeteoResult":
    """Fetch IPCC projections for an explicit year range (non-blocking entry point)."""
    try:
        records, url = await _fetch_projections(latitude, longitude, start_year, end_year)
        logger.info(
            "OpenMeteo projection range: lat=%.4f lon=%.4f years=%d-%d records=%d",
            latitude, longitude, start_year, end_year, len(records),
        )
        return OpenMeteoResult(
            latitude=latitude,
            longitude=longitude,
            projection_records=records,
            projection_url=url,
            model=_PROJECTION_MODEL,
        )
    except Exception as exc:
        logger.warning("fetch_projection_range failed: %s", exc)
        return OpenMeteoResult(latitude=latitude, longitude=longitude, error=str(exc))


async def _fetch_projections(
    latitude: float,
    longitude: float,
    start_year: int = 2024,
    end_year: int = 2050,
) -> tuple[list[ProjectionRecord], str]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{start_year}-01-01",
        "end_date":   f"{end_year}-12-31",
        "models": _PROJECTION_MODEL,
        "daily": "temperature_2m_mean,precipitation_sum",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        req = client.build_request("GET", _PROJECTION_URL, params=params)
        url = str(req.url)
        resp = await client.send(req)
        resp.raise_for_status()
        payload = resp.json()

    daily = payload.get("daily", {})
    dates  = daily.get("time", [])
    temps  = daily.get("temperature_2m_mean", [])
    precip = daily.get("precipitation_sum",   [])

    # Aggregate to annual means/totals
    annual_temps:   dict[int, list[float]] = {}
    annual_precips: dict[int, list[float]] = {}
    for i, date_str in enumerate(dates):
        year = int(date_str[:4])
        t = temps[i]
        p = precip[i]
        if t is not None and float(t) != _FILL:
            annual_temps.setdefault(year, []).append(float(t))
        if p is not None and float(p) != _FILL:
            annual_precips.setdefault(year, []).append(float(p))

    records = [
        ProjectionRecord(
            year=year,
            temp_mean_c=round(sum(annual_temps.get(year, [0])) / max(len(annual_temps.get(year, [1])), 1), 3),
            precip_total_mm=round(sum(annual_precips.get(year, [0])), 1),
        )
        for year in sorted(set(annual_temps) | set(annual_precips))
    ]
    return records, url
