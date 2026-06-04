"""Adapter for Open-Meteo — ERA5 reanalysis, IPCC climate projections, and current forecast."""

import asyncio
import logging
from dataclasses import dataclass, field

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

logger = logging.getLogger(__name__)

_ERA5_URL        = "https://archive-api.open-meteo.com/v1/archive"
_FORECAST_URL    = "https://api.open-meteo.com/v1/forecast"
_PROJECTION_URL  = "https://climate-api.open-meteo.com/v1/climate"
_PROJECTION_MODEL = "EC_Earth3P_HR"  # Default: SSP2-4.5
_FILL = -999.0

# IPCC Shared Socioeconomic Pathways (SSP) scenario mapping
SCENARIO_MODELS = {
    "SSP1-2.6": "MPI_ESM1_2_XR",      # Optimistic: 1.5°C warming
    "SSP2-4.5": "EC_Earth3P_HR",       # Moderate: 2-3°C warming (default)
    "SSP5-8.5": "CMCC_CM2_VHR4",       # Pessimistic: 4-5°C warming
}

SCENARIO_DESCRIPTIONS = {
    "SSP1-2.6": "Optimistic (1.5°C)",
    "SSP2-4.5": "Moderate (2-3°C)",
    "SSP5-8.5": "Pessimistic (4-5°C)",
}


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
    evapotranspiration_mm: float = 0.0


@dataclass
class Era5Record:
    year: int
    temp_mean_c: float
    precip_total_mm: float
    evapotranspiration_mm: float = 0.0
    soil_moisture_m3m3: float = 0.0


@dataclass
class Era5Result:
    latitude: float
    longitude: float
    era5_records: list[Era5Record] = field(default_factory=list)
    era5_url: str = ""
    start_year: int = 0
    end_year: int = 0
    error: str = ""


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


async def fetch_era5_recent(
    latitude: float,
    longitude: float,
    start_year: int = 2026,
    end_year: int = 2026,
) -> Era5Result:
    """Fetch real ERA5 reanalysis data from OpenMeteo archive API.

    ERA5 has ~5-day processing latency. Returns observed data labelled
    source='era5', bridging the gap between the NASA POWER historical
    record (≤ 2025) and IPCC projections (future years).
    """
    import datetime
    today    = datetime.date.today()
    end_date = min(
        datetime.date(end_year, 12, 31),
        today - datetime.timedelta(days=5),
    )
    start_date = datetime.date(start_year, 1, 1)

    if end_date < start_date:
        logger.info(
            "ERA5: no data available yet for %d–%d (today=%s, latency=5d)",
            start_year, end_year, today,
        )
        return Era5Result(latitude=latitude, longitude=longitude,
                          start_year=start_year, end_year=end_year)

    params = {
        "latitude":  latitude,
        "longitude": longitude,
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date":   end_date.strftime("%Y-%m-%d"),
        "daily":     "temperature_2m_mean,precipitation_sum,shortwave_radiation_sum,"
                     "et0_fao_evapotranspiration,soil_moisture_0_to_10cm",
        "timezone":  "auto",
    }

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            req  = client.build_request("GET", _ERA5_URL, params=params)
            url  = str(req.url)
            resp = await client.send(req)
            resp.raise_for_status()
            payload = resp.json()

        daily  = payload.get("daily", {})
        dates  = daily.get("time", [])
        temps  = daily.get("temperature_2m_mean",        [])
        precip = daily.get("precipitation_sum",          [])
        et0    = daily.get("et0_fao_evapotranspiration", [])
        soil   = daily.get("soil_moisture_0_to_10cm",    [])

        annual_temps:   dict[int, list[float]] = {}
        annual_precips: dict[int, list[float]] = {}
        annual_et0:     dict[int, list[float]] = {}
        annual_soil:    dict[int, list[float]] = {}
        for i, date_str in enumerate(dates):
            year = int(date_str[:4])
            t = temps[i]  if i < len(temps)  else None
            p = precip[i] if i < len(precip) else None
            e = et0[i]    if i < len(et0)    else None
            s = soil[i]   if i < len(soil)   else None
            if t is not None and float(t) != _FILL:
                annual_temps.setdefault(year, []).append(float(t))
            if p is not None and float(p) != _FILL:
                annual_precips.setdefault(year, []).append(float(p))
            if e is not None and float(e) != _FILL:
                annual_et0.setdefault(year, []).append(float(e))
            if s is not None and float(s) != _FILL:
                annual_soil.setdefault(year, []).append(float(s))

        def _mean(lst: list[float]) -> float:
            return sum(lst) / len(lst) if lst else 0.0

        records = [
            Era5Record(
                year=year,
                temp_mean_c=round(
                    _mean(annual_temps.get(year, [0])), 3
                ),
                precip_total_mm=round(sum(annual_precips.get(year, [0])), 1),
                evapotranspiration_mm=round(sum(annual_et0.get(year, [0])), 1),
                soil_moisture_m3m3=round(_mean(annual_soil.get(year, [0])), 4),
            )
            for year in sorted(set(annual_temps) | set(annual_precips))
        ]

        logger.info(
            "ERA5 fetch: lat=%.4f lon=%.4f period=%s–%s records=%d",
            latitude, longitude, start_date, end_date, len(records),
        )
        return Era5Result(
            latitude=latitude, longitude=longitude,
            era5_records=records, era5_url=url,
            start_year=start_year, end_year=end_year,
        )

    except Exception as exc:
        logger.warning("ERA5 fetch failed (non-fatal): %s", exc)
        return Era5Result(latitude=latitude, longitude=longitude,
                          start_year=start_year, end_year=end_year, error=str(exc))


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


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _fetch_with_retry(url: str, params: dict) -> dict:
    """Fetch data with automatic retry on network errors."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.get(url, params=params)
        response.raise_for_status()
        return response.json()


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
    scenario: str = "SSP2-4.5",
) -> "OpenMeteoResult":
    """Fetch IPCC projections for an explicit year range with specified scenario."""
    model = SCENARIO_MODELS.get(scenario, SCENARIO_MODELS["SSP2-4.5"])
    try:
        records, url = await _fetch_projections(
            latitude, longitude, start_year, end_year, model
        )
        logger.info(
            "OpenMeteo projection: lat=%.4f lon=%.4f years=%d-%d scenario=%s model=%s records=%d",
            latitude, longitude, start_year, end_year, scenario, model, len(records),
        )
        return OpenMeteoResult(
            latitude=latitude,
            longitude=longitude,
            projection_records=records,
            projection_url=url,
            model=model,
        )
    except Exception as exc:
        logger.warning("fetch_projection_range failed: %s", exc)
        return OpenMeteoResult(latitude=latitude, longitude=longitude, error=str(exc))


async def _fetch_projections(
    latitude: float,
    longitude: float,
    start_year: int = 2024,
    end_year: int = 2050,
    model: str = _PROJECTION_MODEL,
) -> tuple[list[ProjectionRecord], str]:
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "start_date": f"{start_year}-01-01",
        "end_date":   f"{end_year}-12-31",
        "models": model,
        "daily": "temperature_2m_mean,precipitation_sum,et0_fao_evapotranspiration",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        req = client.build_request("GET", _PROJECTION_URL, params=params)
        url = str(req.url)
        resp = await client.send(req)
        resp.raise_for_status()
        payload = resp.json()

    daily = payload.get("daily", {})
    dates  = daily.get("time", [])
    temps  = daily.get("temperature_2m_mean",        [])
    precip = daily.get("precipitation_sum",          [])
    et0    = daily.get("et0_fao_evapotranspiration", [])

    # Aggregate to annual means/totals
    annual_temps:   dict[int, list[float]] = {}
    annual_precips: dict[int, list[float]] = {}
    annual_et0:     dict[int, list[float]] = {}
    for i, date_str in enumerate(dates):
        year = int(date_str[:4])
        t = temps[i]  if i < len(temps)  else None
        p = precip[i] if i < len(precip) else None
        e = et0[i]    if i < len(et0)    else None
        if t is not None and float(t) != _FILL:
            annual_temps.setdefault(year, []).append(float(t))
        if p is not None and float(p) != _FILL:
            annual_precips.setdefault(year, []).append(float(p))
        if e is not None and float(e) != _FILL:
            annual_et0.setdefault(year, []).append(float(e))

    records = [
        ProjectionRecord(
            year=year,
            temp_mean_c=round(
                sum(annual_temps.get(year, [0])) / max(len(annual_temps.get(year, [1])), 1), 3
            ),
            precip_total_mm=round(sum(annual_precips.get(year, [0])), 1),
            evapotranspiration_mm=round(sum(annual_et0.get(year, [0])), 1),
        )
        for year in sorted(set(annual_temps) | set(annual_precips))
    ]
    return records, url
