"""Adapter for the NASA POWER Daily Point API.

Fetches T2M (temperature), PRECTOTCORR (precipitation),
ALLSKY_SFC_SW_DWN (solar irradiance), and EVPTRNS (evapotranspiration)
for a lat/lon bounding box, then aggregates daily values into annual statistics.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import httpx
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from ..core.config import (
    NASA_DEFAULT_END_YEAR,
    NASA_DEFAULT_START_YEAR,
    NASA_POWER_BASE_URL,
)

logger = logging.getLogger(__name__)

_PARAMETERS = "T2M,PRECTOTCORR,ALLSKY_SFC_SW_DWN,EVPTRNS"
_FILL_VALUE = -999.0

TEMP_RANGE   = (-5.0, 40.0)
PRECIP_RANGE = (0.0, 4000.0)
SOLAR_RANGE  = (0.0, 10.0)


def filter_valid_records(records: list, region: str) -> list:
    """Drop records whose temperature, precipitation, or solar is outside physical bounds."""
    valid = []
    discarded = 0
    total = len(records)
    for r in records:
        temp   = float(getattr(r, "temp_mean_celsius", 0) or 0)
        precip = float(getattr(r, "precip_total_mm",   0) or 0)
        solar  = float(getattr(r, "solar_mean_kwh_m2", 0) or 0)
        if temp != 0.0 and not (TEMP_RANGE[0] <= temp <= TEMP_RANGE[1]):
            logger.warning(
                "Discarded NASA record for %r year=%s: temp=%.2f°C out of range %s",
                region, getattr(r, "year", "?"), temp, TEMP_RANGE,
            )
            discarded += 1
            continue
        if precip != 0.0 and not (PRECIP_RANGE[0] <= precip <= PRECIP_RANGE[1]):
            logger.warning(
                "Discarded NASA record for %r year=%s: precip=%.1fmm out of range %s",
                region, getattr(r, "year", "?"), precip, PRECIP_RANGE,
            )
            discarded += 1
            continue
        if solar != 0.0 and not (SOLAR_RANGE[0] <= solar <= SOLAR_RANGE[1]):
            logger.warning(
                "Discarded NASA record for %r year=%s: solar=%.2f kWh/m² out of range %s",
                region, getattr(r, "year", "?"), solar, SOLAR_RANGE,
            )
            discarded += 1
            continue
        valid.append(r)
    if discarded:
        logger.warning("%d/%d NASA records discarded for %r due to invalid values", discarded, total, region)
    return valid


@dataclass
class AnnualClimateRecord:
    year: int
    latitude: float
    longitude: float
    temp_mean_celsius: float
    temp_max_celsius: float
    temp_min_celsius: float
    precip_total_mm: float
    solar_mean_kwh_m2: float
    evapotranspiration_mm: float
    days_sampled: int


@dataclass
class NasaClimateResult:
    latitude: float
    longitude: float
    region_label: str
    annual_records: list[AnnualClimateRecord] = field(default_factory=list)
    source: str = "NASA POWER API v2.5"
    parameters_fetched: list[str] = field(
        default_factory=lambda: _PARAMETERS.split(",")
    )
    request_url: str = ""
    request_params: dict = field(default_factory=dict)
    total_daily_datapoints: int = 0


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
    reraise=True,
)
async def _fetch_nasa_with_retry(
    client: httpx.AsyncClient,
    params: dict,
) -> dict:
    """Fetch NASA data with automatic retry on network errors."""
    prepared = client.build_request("GET", NASA_POWER_BASE_URL, params=params)
    response = await client.send(prepared)
    response.raise_for_status()
    return response.json()


async def fetch_climate_data(
    latitude: float,
    longitude: float,
    region_label: str = "",
    start_year: int = NASA_DEFAULT_START_YEAR,
    end_year: int = NASA_DEFAULT_END_YEAR,
) -> NasaClimateResult:
    """Fetch daily climate data from NASA POWER and return annual aggregates.
    
    Includes automatic retry logic for network errors (up to 3 attempts).
    """
    params = {
        "parameters": _PARAMETERS,
        "community": "RE",
        "longitude": longitude,
        "latitude": latitude,
        "start": f"{start_year}0101",
        "end": f"{end_year}1231",
        "format": "JSON",
    }

    logger.info(
        "NASA POWER request: region=%r lat=%.4f lon=%.4f years=%d-%d",
        region_label or "(unnamed)",
        latitude,
        longitude,
        start_year,
        end_year,
    )

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            prepared = client.build_request("GET", NASA_POWER_BASE_URL, params=params)
            request_url = str(prepared.url)
            
            # Use retry wrapper for network resilience
            payload = await _fetch_nasa_with_retry(client, params)
    except httpx.HTTPStatusError as e:
        logger.error(
            "NASA POWER API error: status=%d url=%s",
            e.response.status_code,
            e.request.url,
        )
        raise ValueError(
            f"NASA POWER API returned error {e.response.status_code}. "
            "Please check coordinates and try again."
        ) from e
    except httpx.TimeoutException as e:
        logger.error("NASA POWER API timeout after retries: %s", e)
        raise ValueError(
            "NASA POWER API timeout. The service may be temporarily unavailable."
        ) from e
    except httpx.NetworkError as e:
        logger.error("NASA POWER API network error after retries: %s", e)
        raise ValueError(
            "Network error connecting to NASA POWER API. Please check your connection."
        ) from e

    raw_parameters = payload["properties"]["parameter"]
    annual_records = _aggregate_by_year(raw_parameters, latitude, longitude)
    annual_records = filter_valid_records(annual_records, region_label or f"{latitude:.4f},{longitude:.4f}")

    total_daily_datapoints = sum(
        len([v for v in raw_parameters.get(p, {}).values() if v != _FILL_VALUE])
        for p in ["T2M", "PRECTOTCORR", "ALLSKY_SFC_SW_DWN", "EVPTRNS"]
    )

    logger.info(
        "NASA POWER response: region=%r annual_records=%d datapoints=%d",
        region_label or "(unnamed)",
        len(annual_records),
        total_daily_datapoints,
    )

    return NasaClimateResult(
        latitude=latitude,
        longitude=longitude,
        region_label=region_label or f"{latitude:.4f},{longitude:.4f}",
        annual_records=annual_records,
        request_url=request_url,
        request_params=params,
        total_daily_datapoints=total_daily_datapoints,
    )


def _aggregate_by_year(
    parameters: dict[str, dict[str, float]],
    latitude: float,
    longitude: float,
) -> list[AnnualClimateRecord]:
    """Group daily NASA values by calendar year and compute statistics."""
    temps: dict[int, list[float]] = {}
    precips: dict[int, list[float]] = {}
    solars: dict[int, list[float]] = {}
    et0s: dict[int, list[float]] = {}

    for date_key, value in parameters.get("T2M", {}).items():
        if value != _FILL_VALUE:
            temps.setdefault(int(date_key[:4]), []).append(value)

    for date_key, value in parameters.get("PRECTOTCORR", {}).items():
        if value != _FILL_VALUE:
            precips.setdefault(int(date_key[:4]), []).append(value)

    for date_key, value in parameters.get("ALLSKY_SFC_SW_DWN", {}).items():
        if value != _FILL_VALUE:
            solars.setdefault(int(date_key[:4]), []).append(value)

    for date_key, value in parameters.get("EVPTRNS", {}).items():
        if value != _FILL_VALUE:
            et0s.setdefault(int(date_key[:4]), []).append(value)

    all_years = sorted(set(temps) | set(precips) | set(solars))

    records = []
    for year in all_years:
        t = temps.get(year, [])
        p = precips.get(year, [])
        s = solars.get(year, [])
        e = et0s.get(year, [])

        records.append(
            AnnualClimateRecord(
                year=year,
                latitude=latitude,
                longitude=longitude,
                temp_mean_celsius=_mean(t),
                temp_max_celsius=round(max(t), 2) if t else 0.0,
                temp_min_celsius=round(min(t), 2) if t else 0.0,
                precip_total_mm=round(sum(p), 1) if p else 0.0,
                solar_mean_kwh_m2=_mean(s),
                evapotranspiration_mm=round(sum(e), 1) if e else 0.0,
                days_sampled=max(len(t), len(p), len(s)),
            )
        )

    return records


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 3) if values else 0.0
