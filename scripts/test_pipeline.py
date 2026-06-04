"""End-to-end pipeline smoke test — all 4 agents, real NASA + Claude calls.

Usage:
    python3 scripts/test_pipeline.py
    python3 scripts/test_pipeline.py --lat -23.55 --lon -46.63 --label "São Paulo"
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.aesg.pipeline.orchestrator import run_analysis

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
)

DEFAULT_LAT = -15.78
DEFAULT_LON = -47.93
DEFAULT_LABEL = "Brasília, Brazil"


async def run(lat: float, lon: float, label: str) -> None:
    result = await run_analysis(
        latitude=lat,
        longitude=lon,
        region_label=label,
        start_year=2014,
        end_year=2023,
    )

    print("\n" + "═" * 70)
    print(f"  Analysis ID : {result.analysis_id}")
    print(f"  Region      : {result.region_label}")
    print(f"  Duration    : {result.pipeline_duration_sec}s")
    print("═" * 70)
    print(f"  Risk Score  : {result.risk_score}/100")
    print(f"  Risk Level  : {result.risk_level.upper()}")
    print(f"  Badge       : {result.risk_badge_label}")
    print("─" * 70)
    print(f"  Summary:\n  {result.executive_summary}")
    print("─" * 70)
    print(f"  Key Metrics : {json.dumps(result.key_metrics, indent=4)}")
    print("─" * 70)
    print(f"  Recommendations ({len(result.recommendations)}):")
    for rec in result.recommendations:
        print(
            f"    [{rec.get('rank')}] [{rec.get('framework')}] "
            f"{rec.get('action')} ({rec.get('timeline')})"
        )
    print("─" * 70)
    print(f"  Climate findings keys : {list(result.climate_findings.keys())}")
    print(f"  Compliance keys       : {list(result.compliance_mapping.keys())}")
    print("═" * 70 + "\n")

    assert result.risk_score >= 0, "risk_score must be >= 0"
    assert result.risk_level in ("low", "medium", "high", "critical"), f"Unexpected risk_level: {result.risk_level}"
    assert result.executive_summary, "executive_summary is empty"
    assert result.recommendations, "recommendations list is empty"

    logging.getLogger(__name__).info("Pipeline OK — all 4 agents completed successfully.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lat", type=float, default=DEFAULT_LAT)
    parser.add_argument("--lon", type=float, default=DEFAULT_LON)
    parser.add_argument("--label", type=str, default=DEFAULT_LABEL)
    args = parser.parse_args()

    asyncio.run(run(args.lat, args.lon, args.label))


if __name__ == "__main__":
    main()
