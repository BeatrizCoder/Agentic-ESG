"""CS analysis pipeline — sequential orchestration of the 4 agents."""

import asyncio
import json
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ..data.nasa_adapter import AnnualClimateRecord, NasaClimateResult, fetch_climate_data
from ..data.openmeteo_adapter import (
    OpenMeteoResult, fetch_projection_range, _PROJECTION_MODEL,
)

logger = logging.getLogger(__name__)


def _climate_summary_for_agents(findings: dict) -> str:
    """Extract the compact key-value fields that downstream agents need."""
    keys = (
        "temp_trend_c_per_decade", "precip_trend_pct_per_decade",
        "heat_stress_risk", "drought_risk", "flood_risk", "solar_trend",
        "hottest_year", "driest_year", "wettest_year",
        "baseline_temp_mean_c", "latest_temp_mean_c",
        "baseline_precip_mm", "latest_precip_mm",
        "temp_anomaly_years", "precip_anomaly_years",
        "key_findings", "data_quality",
    )
    compact = {k: findings.get(k) for k in keys if findings.get(k) is not None}
    return json.dumps(compact, indent=2)


def _compliance_summary_for_agents(mapping: dict) -> str:
    keys = (
        "csrd_exposure", "csrd_articles", "csrd_summary",
        "issb_s2_exposure", "issb_s2_scenarios", "issb_s2_summary",
        "eu_taxonomy_alignment", "eu_taxonomy_criteria",
        "compliance_urgency", "priority_framework",
        "key_compliance_findings",
    )
    compact = {k: mapping.get(k) for k in keys if mapping.get(k) is not None}
    return json.dumps(compact, indent=2)


@dataclass
class AnalysisResult:
    analysis_id: str
    region_label: str
    latitude: float
    longitude: float
    risk_score: int
    risk_level: str
    risk_badge_label: str
    executive_summary: str
    recommendations: list[dict[str, Any]]
    key_metrics: dict[str, Any]
    climate_findings: dict[str, Any]
    compliance_mapping: dict[str, Any]
    annual_records: list[dict[str, Any]]
    created_at: str
    pipeline_duration_sec: float
    pipeline_metadata: dict[str, Any] = field(default_factory=dict)
    confidence_score: int = 0
    quality_evaluation: dict[str, Any] = field(default_factory=dict)
    openmeteo_data: dict[str, Any] = field(default_factory=dict)
    offset_targets: list[dict[str, Any]] = field(default_factory=list)
    sector: str = "General"
    error: str = ""


async def run_analysis(
    latitude: float,
    longitude: float,
    region_label: str = "",
    start_year: int = 2014,
    end_year: int = 2023,
    sector: str = "General",
) -> AnalysisResult:
    """
    Full CS pipeline:
      1. Data Collector  — NASA POWER fetch (Python, no LLM)
      2. Climate Analyst — trend + anomaly detection (Haiku)
      3. ESG Strategist  — compliance mapping (Sonnet)
      4. Report Writer   — risk score + report (Sonnet)
    """
    pipeline_start = time.time()
    analysis_id = f"CS-{int(time.time())}"
    label = region_label or f"{latitude:.4f},{longitude:.4f}"

    logger.info("Pipeline start: analysis_id=%s region=%r", analysis_id, label)

    # ── Step 1: Data Collector ─────────────────────────────────────────────────
    # 2000–2025 → NASA POWER (real observations)
    # 2026–2050 → OpenMeteo IPCC EC_Earth3P_HR (projection)
    nasa_end_year    = min(end_year, 2025)
    needs_projection = end_year > 2025
    om_start_year    = 2026

    if needs_projection:
        logger.info(
            "Step 1/5 — Data Collector: NASA (%d–%d) + OpenMeteo IPCC (%d–%d) in parallel",
            start_year, nasa_end_year, om_start_year, end_year,
        )
        _nasa_task = fetch_climate_data(
            latitude=latitude, longitude=longitude, region_label=label,
            start_year=start_year, end_year=nasa_end_year,
        )
        _om_task = fetch_projection_range(latitude, longitude, om_start_year, end_year)
        nasa_result, om_raw = await asyncio.gather(_nasa_task, _om_task, return_exceptions=True)
    else:
        logger.info("Step 1/5 — Data Collector: NASA POWER (%d–%d) only", start_year, nasa_end_year)
        nasa_result = await fetch_climate_data(
            latitude=latitude, longitude=longitude, region_label=label,
            start_year=start_year, end_year=nasa_end_year,
        )
        om_raw = None

    if isinstance(nasa_result, Exception):
        raise nasa_result

    if isinstance(om_raw, Exception):
        logger.warning("OpenMeteo IPCC fetch failed (non-fatal): %s", om_raw)
        om_raw = OpenMeteoResult(latitude=latitude, longitude=longitude, error=str(om_raw))

    om_result: OpenMeteoResult = om_raw or OpenMeteoResult(latitude=latitude, longitude=longitude)

    # ── Build unified annual dataset (source field = "nasa" | "projection") ───
    unified_records: list[dict] = [
        {
            "year":              r.year,
            "latitude":          r.latitude,
            "longitude":         r.longitude,
            "temp_mean_celsius": r.temp_mean_celsius,
            "temp_max_celsius":  r.temp_max_celsius,
            "temp_min_celsius":  r.temp_min_celsius,
            "precip_total_mm":   r.precip_total_mm,
            "solar_mean_kwh_m2": r.solar_mean_kwh_m2,
            "days_sampled":      r.days_sampled,
            "source":            "nasa",
        }
        for r in nasa_result.annual_records
    ]
    if needs_projection and om_result.projection_records:
        unified_records += [
            {
                "year":              r.year,
                "latitude":          latitude,
                "longitude":         longitude,
                "temp_mean_celsius": r.temp_mean_c,
                "temp_max_celsius":  None,
                "temp_min_celsius":  None,
                "precip_total_mm":   r.precip_total_mm,
                "solar_mean_kwh_m2": None,
                "days_sampled":      365,
                "source":            "projection",
            }
            for r in om_result.projection_records
        ]

    serialised_records = json.dumps([
        {
            "year":            r["year"],
            "temp_mean_c":     r.get("temp_mean_celsius") or 0,
            "precip_total_mm": r.get("precip_total_mm") or 0,
            "solar_mean_kwh_m2": r.get("solar_mean_kwh_m2"),
            "source":          r["source"],
        }
        for r in unified_records
    ])

    logger.info(
        "Step 1/5 complete: nasa=%d years  projection=%d years  total=%d",
        len(nasa_result.annual_records),
        len(om_result.projection_records),
        len(unified_records),
    )

    # ── Step 2: Climate Analyst ────────────────────────────────────────────────
    from ..agents.crews import run_climate_analysis_crew

    logger.info("Step 2/5 — Climate Analyst: analysing trends")
    climate_findings, tokens_analyst = await run_climate_analysis_crew(serialised_records)
    logger.info(
        "Step 2/4 complete: heat_stress=%s drought=%s flood=%s tokens=%s",
        climate_findings.get("heat_stress_risk"),
        climate_findings.get("drought_risk"),
        climate_findings.get("flood_risk"),
        tokens_analyst.get("total_tokens"),
    )

    # ── Step 3: ESG Strategist ─────────────────────────────────────────────────
    from ..agents.crews import run_esg_strategy_crew

    logger.info("Step 3/5 — ESG Strategist: mapping compliance frameworks")
    climate_summary = _climate_summary_for_agents(climate_findings)
    compliance_mapping, tokens_strategist = await run_esg_strategy_crew(
        climate_summary=climate_summary,
        region_label=label,
        sector=sector,
    )
    logger.info(
        "Step 3/4 complete: csrd=%s issb_s2=%s urgency=%s tokens=%s",
        compliance_mapping.get("csrd_exposure"),
        compliance_mapping.get("issb_s2_exposure"),
        compliance_mapping.get("compliance_urgency"),
        tokens_strategist.get("total_tokens"),
    )

    # ── Step 4: Report Writer ──────────────────────────────────────────────────
    from ..agents.crews import run_report_crew

    logger.info("Step 4/5 — Report Writer: generating executive report")
    compliance_summary = _compliance_summary_for_agents(compliance_mapping)
    report, tokens_writer = await run_report_crew(
        climate_summary=climate_summary,
        compliance_summary=compliance_summary,
        region_label=label,
        latitude=latitude,
        longitude=longitude,
    )
    logger.info(
        "Step 4/4 complete: risk_score=%s risk_level=%s tokens=%s",
        report.get("risk_score"),
        report.get("risk_level"),
        tokens_writer.get("total_tokens"),
    )

    pipeline_duration = round(time.time() - pipeline_start, 2)
    logger.info(
        "Pipeline complete: analysis_id=%s duration=%.1fs risk_score=%s",
        analysis_id,
        pipeline_duration,
        report.get("risk_score"),
    )

    # ── Step 5: Quality Judge ──────────────────────────────────────────────────
    from ..agents.crews import run_quality_judge_crew

    logger.info("Step 5/5 — Quality Judge: validating report")
    report_summary_for_judge = json.dumps({
        "risk_score":  report.get("risk_score"),
        "risk_level":  report.get("risk_level"),
        "summary_excerpt": report.get("executive_summary", "")[:200],
        "recs": [
            {"fw": r.get("framework"), "art": r.get("article")}
            for r in report.get("recommendations", [])[:5]
        ],
    })
    quality_evaluation, tokens_judge = await run_quality_judge_crew(
        climate_summary=climate_summary,
        compliance_summary=compliance_summary,
        report_summary=report_summary_for_judge,
    )
    confidence_score = int(quality_evaluation.get("confidence_score", 0))
    logger.info(
        "Step 5/5 complete: confidence=%s verdict=%s tokens=%s",
        confidence_score,
        quality_evaluation.get("verdict"),
        tokens_judge.get("total_tokens"),
    )

    total_llm_tokens = (
        tokens_analyst.get("total_tokens", 0)
        + tokens_strategist.get("total_tokens", 0)
        + tokens_writer.get("total_tokens", 0)
        + tokens_judge.get("total_tokens", 0)
    )

    pipeline_metadata = {
        "nasa_request_url":          nasa_result.request_url,
        "nasa_params":               nasa_result.request_params,
        "nasa_start_year":           start_year,
        "nasa_end_year":             nasa_end_year,
        "nasa_records_count":        len(nasa_result.annual_records),
        "total_daily_datapoints":    nasa_result.total_daily_datapoints,
        "openmeteo_used":            needs_projection,
        "openmeteo_projection_url":  om_result.projection_url or None,
        "openmeteo_model":           _PROJECTION_MODEL if needs_projection else None,
        "openmeteo_start_year":      om_start_year if needs_projection else None,
        "openmeteo_end_year":        end_year if needs_projection else None,
        "openmeteo_projection_years": len(om_result.projection_records),
        "openmeteo_error":           om_result.error or None,
        "total_records":             len(unified_records),
        "total_llm_tokens":          total_llm_tokens,
        "agents": [
            {
                "step": 1, "name": "Data Collector",
                "model": "Python + httpx (no LLM)",
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            },
            {
                "step": 2, "name": "Climate Analyst",
                "model": "claude-haiku-4-5",
                **tokens_analyst,
            },
            {
                "step": 3, "name": "ESG Strategist",
                "model": "claude-sonnet-4-6",
                **tokens_strategist,
            },
            {
                "step": 4, "name": "Report Writer",
                "model": "claude-sonnet-4-6",
                **tokens_writer,
            },
            {
                "step": 5, "name": "Quality Judge",
                "model": "claude-sonnet-4-6",
                **tokens_judge,
            },
        ],
    }

    return AnalysisResult(
        analysis_id=analysis_id,
        region_label=label,
        latitude=latitude,
        longitude=longitude,
        risk_score=report.get("risk_score", 0),
        risk_level=report.get("risk_level", "unknown"),
        risk_badge_label=report.get("risk_badge_label", ""),
        executive_summary=report.get("executive_summary", ""),
        recommendations=report.get("recommendations", []),
        key_metrics=report.get("key_metrics", {}),
        climate_findings=climate_findings,
        compliance_mapping=compliance_mapping,
        annual_records=unified_records,
        created_at=datetime.utcnow().isoformat() + "Z",
        pipeline_duration_sec=pipeline_duration,
        pipeline_metadata=pipeline_metadata,
        confidence_score=confidence_score,
        quality_evaluation=quality_evaluation,
        offset_targets=report.get("offset_targets", []),
        sector=sector,
        openmeteo_data={
            "used":               needs_projection,
            "projection_url":     om_result.projection_url,
            "model":              _PROJECTION_MODEL,
            "start_year":         om_start_year if needs_projection else None,
            "end_year":           end_year if needs_projection else None,
            "projection_records": [asdict(r) for r in om_result.projection_records],
            "error":              om_result.error,
        },
        error=report.get("error", ""),
    )
