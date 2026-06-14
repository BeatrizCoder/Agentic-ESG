"""Adapter for Open-Meteo — ERA5 reanalysis, IPCC climate projections, and current forecast."""

import asyncio
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

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
_PROJECTION_MODEL = "EC_Earth3P_HR"  # kept for backward compat
_PROJECTION_ENSEMBLE = ",".join([
    "CMCC_CM2_VHR4",
    "MRI_AGCM3_2_S",
    "EC_Earth3P_HR",
    "MPI_ESM1_2_XR",
    "NICAM16_8S",
])

TEMP_RANGE   = (-5.0, 40.0)
PRECIP_RANGE = (0.0, 4000.0)
SOLAR_RANGE  = (0.0, 10.0)


def filter_valid_records(records: list, region: str) -> list:
    """Drop records whose temperature or precipitation is outside physical bounds."""
    valid = []
    discarded = 0
    total = len(records)
    for r in records:
        temp   = getattr(r, "temp_mean_c", None) or getattr(r, "temp_mean_celsius", None) or 0.0
        precip = getattr(r, "precip_total_mm", None) or 0.0
        if temp != 0.0 and not (TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]):
            logger.warning(
                "Discarded record for %r year=%s: temp=%.2f°C out of range %s",
                region, getattr(r, "year", "?"), temp, TEMP_RANGE,
            )
            discarded += 1
            continue
        if precip != 0.0 and not (PRECIP_RANGE[0] <= precip <= PRECIP_RANGE[1]):
            logger.warning(
                "Discarded record for %r year=%s: precip=%.1fmm out of range %s",
                region, getattr(r, "year", "?"), precip, PRECIP_RANGE,
            )
            discarded += 1
            continue
        valid.append(r)
    if discarded:
        logger.warning("%d/%d records discarded for %r due to invalid values", discarded, total, region)
    return valid
_FILL = -999.0


def aggregate_daily_to_annual(
    dates: List[str],
    values: List[Optional[float]],
    method: str = "mean",
) -> Dict[int, float]:
    """Group daily values by year and reduce to annual mean or sum."""
    yearly: Dict[int, List[float]] = defaultdict(list)
    for date_str, val in zip(dates, values):
        if val is None or val == -999.0:
            continue
        year = int(date_str[:4])
        yearly[year].append(float(val))
    result: Dict[int, float] = {}
    for year, vals in yearly.items():
        if not vals:
            continue
        result[year] = sum(vals) / len(vals) if method == "mean" else sum(vals)
    return result

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


def get_era5_safe_end_date() -> str:
    """Return today minus 7 days — safely within ERA5's ~7-day processing latency."""
    safe = date.today() - timedelta(days=7)
    return safe.strftime("%Y-%m-%d")


async def fetch_era5_recent(
    latitude: float,
    longitude: float,
    start_year: int = 2026,
    end_year: int = 2026,
) -> Era5Result:
    """Fetch real ERA5 reanalysis data from OpenMeteo archive API.

    ERA5 has ~7-day processing latency. Returns observed data labelled
    source='era5', bridging the gap between the NASA POWER historical
    record (≤ 2025) and IPCC projections (future years).
    """
    end_date_str = get_era5_safe_end_date()
    end_date   = date.fromisoformat(end_date_str)
    start_date = date(start_year, 1, 1)

    if end_date < start_date:
        logger.info(
            "ERA5: no data available yet for %d–%d (latency=7d)",
            start_year, end_year,
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

        records = filter_valid_records(records, f"era5:{latitude:.4f},{longitude:.4f}")
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


async def fetch_ipcc_projections(
    lat: float,
    lon: float,
    start_year: int = 2026,
    end_year: int = 2050,
    scenario: str = "SSP2-4.5",
) -> Tuple[Dict[int, float], Dict[int, float]]:
    """Fetch IPCC projections and return (annual_temps, annual_precips) dicts.

    Requests the 5-model ensemble. OpenMeteo may return per-model columns
    (e.g. temperature_2m_mean_CMCC_CM2_VHR4) rather than a single averaged
    field — this function averages all matching columns explicitly.
    """
    params = {
        "latitude":   lat,
        "longitude":  lon,
        "start_date": f"{start_year}-01-01",
        "end_date":   f"{end_year}-12-31",
        "models":     _PROJECTION_ENSEMBLE,
        "daily":      "temperature_2m_mean,precipitation_sum",
        "timezone":   "UTC",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(_PROJECTION_URL, params=params)
        response.raise_for_status()
        data = response.json()

    daily_data = data.get("daily", {})
    dates = daily_data.get("time", [])
    if not dates:
        logger.warning("OpenMeteo: no dates returned for %.4f,%.4f", lat, lon)
        return {}, {}

    temp_fields   = [k for k in daily_data if k.startswith("temperature_2m_mean")]
    precip_fields = [k for k in daily_data if k.startswith("precipitation_sum")]

    logger.info("OpenMeteo ensemble temp fields:   %s", temp_fields)
    logger.info("OpenMeteo ensemble precip fields: %s", precip_fields)

    n_days = len(dates)
    daily_temps:  List[Optional[float]] = []
    daily_precips: List[Optional[float]] = []

    for i in range(n_days):
        temp_vals = [
            daily_data[f][i]
            for f in temp_fields
            if i < len(daily_data[f]) and daily_data[f][i] is not None and daily_data[f][i] != _FILL
        ]
        daily_temps.append(sum(temp_vals) / len(temp_vals) if temp_vals else None)

    for i in range(n_days):
        prec_vals = [
            daily_data[f][i]
            for f in precip_fields
            if i < len(daily_data[f]) and daily_data[f][i] is not None and daily_data[f][i] != _FILL
        ]
        daily_precips.append(sum(prec_vals) / len(prec_vals) if prec_vals else None)

    logger.info("First 10 dates: %s", dates[:10])
    logger.info("First 10 ensemble temps:  %s", [round(t, 2) if t is not None else None for t in daily_temps[:10]])
    logger.info("First 10 ensemble precip: %s", [round(p, 2) if p is not None else None for p in daily_precips[:10]])

    annual_temps   = aggregate_daily_to_annual(dates, daily_temps,  method="mean")
    annual_precips = aggregate_daily_to_annual(dates, daily_precips, method="sum")

    logger.info("Annual temps all years:  %s", {k: round(v, 2) for k, v in annual_temps.items()})
    logger.info("Annual precip all years: %s", {k: round(v, 1) for k, v in annual_precips.items()})

    for year, precip in list(annual_precips.items()):
        if precip > 3000:
            logger.error(
                "Precipitation %.0fmm for %d is impossible — removing from results",
                precip, year,
            )
            del annual_precips[year]
        elif precip < 5:
            logger.warning(
                "Precipitation %.0fmm for %d is suspiciously low",
                precip, year,
            )

    unique_temps = set(round(t, 1) for t in annual_temps.values())
    if len(annual_temps) > 1 and len(unique_temps) < 2:
        logger.error(
            "OpenMeteo: projection temperatures still constant %s (lat=%.4f lon=%.4f)",
            unique_temps, lat, lon,
        )

    logger.info(
        "OpenMeteo: %d projection years retrieved (lat=%.4f lon=%.4f scenario=%s)",
        len(annual_temps), lat, lon, scenario,
    )
    return annual_temps, annual_precips


async def fetch_projection_range(
    latitude: float,
    longitude: float,
    start_year: int = 2026,
    end_year: int = 2050,
    scenario: str = "SSP2-4.5",
) -> "OpenMeteoResult":
    """Fetch IPCC projections and return an OpenMeteoResult with ProjectionRecords."""
    try:
        annual_temps, annual_precips = await fetch_ipcc_projections(
            latitude, longitude, start_year, end_year, scenario
        )
        all_years = sorted(set(annual_temps) | set(annual_precips))
        records = [
            ProjectionRecord(
                year=year,
                temp_mean_c=round(annual_temps[year], 3) if year in annual_temps else 0.0,
                precip_total_mm=round(annual_precips.get(year, 0.0), 1),
            )
            for year in all_years
        ]
        records = filter_valid_records(records, f"projection:{latitude:.4f},{longitude:.4f}")
        logger.info(
            "fetch_projection_range: lat=%.4f lon=%.4f years=%d-%d scenario=%s records=%d",
            latitude, longitude, start_year, end_year, scenario, len(records),
        )
        return OpenMeteoResult(
            latitude=latitude,
            longitude=longitude,
            projection_records=records,
            projection_url=f"{_PROJECTION_URL}?models={_PROJECTION_ENSEMBLE}",
            model=_PROJECTION_ENSEMBLE,
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
        "latitude":   latitude,
        "longitude":  longitude,
        "start_date": f"{start_year}-01-01",
        "end_date":   f"{end_year}-12-31",
        "models":     _PROJECTION_ENSEMBLE,
        "daily":      "temperature_2m_mean,precipitation_sum,et0_fao_evapotranspiration",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        req = client.build_request("GET", _PROJECTION_URL, params=params)
        url = str(req.url)
        resp = await client.send(req)
        resp.raise_for_status()
        payload = resp.json()

    daily = payload.get("daily", {})
    logger.info("OpenMeteo projection fields: %s", list(daily.keys()))

    dates  = daily.get("time", [])
    temps  = daily.get("temperature_2m_mean",        [])
    precip = daily.get("precipitation_sum",          [])
    et0    = daily.get("et0_fao_evapotranspiration", [])

    logger.info("Raw temp values (first 10 days): %s", temps[:10])
    logger.info(
        "Temperature unit check: if values > 200, likely Kelvin. First non-null: %s",
        next((t for t in temps if t is not None), None),
    )

    # Kelvin → Celsius conversion if the API returns absolute temperature
    if temps and any(t is not None and t > 200 for t in temps[:10]):
        temps = [t - 273.15 if t is not None else None for t in temps]
        logger.info("Converted Kelvin → Celsius (first value now: %s)", temps[0])

    # Count valid daily values per year before reducing — used for debug logging
    yearly_counts: dict[int, int] = {}
    for date, val in zip(dates, temps):
        if val is not None and float(val) != _FILL:
            year = int(date[:4])
            yearly_counts[year] = yearly_counts.get(year, 0) + 1

    annual_temps   = aggregate_daily_to_annual(dates, temps,  method="mean")
    annual_precips = aggregate_daily_to_annual(dates, precip, method="sum")
    annual_et0     = aggregate_daily_to_annual(dates, et0,    method="sum")

    for year, mean_temp in sorted(annual_temps.items()):
        logger.info(
            "Year %d: %d days, mean=%.2f°C",
            year, yearly_counts.get(year, 0), mean_temp,
        )

    # Sanity check: warn on implausible individual values
    for year, temp in annual_temps.items():
        if temp < 10 or temp > 40:
            logger.warning(
                "Suspicious projection temp %.2f°C for year %d (lat=%.4f lon=%.4f)",
                temp, year, latitude, longitude,
            )

    # Sanity check: constant temperatures indicate broken aggregation
    if len(annual_temps) >= 3:
        unique_rounded = set(round(t, 1) for t in annual_temps.values())
        if len(unique_rounded) < 3:
            logger.error(
                "Projection temperatures appear constant (%s) — "
                "ensemble aggregation may be broken (lat=%.4f lon=%.4f)",
                unique_rounded, latitude, longitude,
            )
            return [], url

    records = [
        ProjectionRecord(
            year=year,
            temp_mean_c=round(annual_temps[year], 3) if year in annual_temps else 0.0,
            precip_total_mm=round(annual_precips.get(year, 0.0), 1),
            evapotranspiration_mm=round(annual_et0.get(year, 0.0), 1),
        )
        for year in sorted(set(annual_temps) | set(annual_precips))
    ]

    if records:
        sample = [(r.year, r.temp_mean_c) for r in records[:3]]
        logger.info("Aggregated projected temp_mean_c sample: %s", sample)
        valid_temps = [r.temp_mean_c for r in records if r.temp_mean_c != 0.0]
        if valid_temps:
            mean_t = sum(valid_temps) / len(valid_temps)
            if mean_t < 5.0:
                logger.warning(
                    "Projected mean temperature %.2f°C looks low — "
                    "verify temperature_2m_mean is in ensemble response "
                    "(lat=%.4f lon=%.4f). Check for fill values or unit issues.",
                    mean_t, latitude, longitude,
                )

    records = filter_valid_records(records, f"projection:{latitude:.4f},{longitude:.4f}")
    return records, url
