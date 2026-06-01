"""Smoke test — confirm real data arrives from NASA POWER API.

Usage:
    python scripts/test_nasa_adapter.py
    python scripts/test_nasa_adapter.py --lat -23.55 --lon -46.63 --label "São Paulo"
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

# Make src importable when running from repo root
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.cs.data.nasa_adapter import fetch_climate_data

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Defaults: Brasília, Brazil
DEFAULT_LAT = -15.78
DEFAULT_LON = -47.93
DEFAULT_LABEL = "Brasília, Brazil"
DEFAULT_START = 2019
DEFAULT_END = 2023


async def run(lat: float, lon: float, label: str, start: int, end: int) -> None:
    logger.info("Testing NASA POWER adapter for %r ...", label)

    result = await fetch_climate_data(
        latitude=lat,
        longitude=lon,
        region_label=label,
        start_year=start,
        end_year=end,
    )

    print("\n" + "═" * 60)
    print(f"  Region : {result.region_label}")
    print(f"  Source : {result.source}")
    print(f"  Records: {len(result.annual_records)} years")
    print("═" * 60)

    for rec in result.annual_records:
        print(
            f"  {rec.year}  "
            f"T_mean={rec.temp_mean_celsius:6.2f}°C  "
            f"T_max={rec.temp_max_celsius:6.2f}°C  "
            f"T_min={rec.temp_min_celsius:6.2f}°C  "
            f"Precip={rec.precip_total_mm:7.1f}mm  "
            f"Solar={rec.solar_mean_kwh_m2:.3f} kWh/m²  "
            f"({rec.days_sampled}d)"
        )

    print("═" * 60)
    print()

    if not result.annual_records:
        logger.error("No records returned — check coordinates or API availability.")
        sys.exit(1)

    last = result.annual_records[-1]
    assert last.temp_mean_celsius != 0.0, "Temperature data looks empty"
    assert last.precip_total_mm > 0.0, "Precipitation data looks empty"

    logger.info("Adapter OK — real NASA data confirmed.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Test NASA POWER adapter")
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--label", type=str, default=DEFAULT_LABEL)
    parser.add_argument("--start", type=int, default=DEFAULT_START)
    parser.add_argument("--end", type=int, default=DEFAULT_END)
    args = parser.parse_args()

    asyncio.run(run(args.lat, args.lon, args.label, args.start, args.end))


if __name__ == "__main__":
    main()
