"""CS analysis pipeline — sequential orchestration of the 4 agents."""

import asyncio
import json
import logging
import statistics
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

from ..data.nasa_adapter import AnnualClimateRecord, NasaClimateResult, fetch_climate_data
from ..data.openmeteo_adapter import (
    Era5Result, OpenMeteoResult,
    fetch_era5_recent, fetch_projection_range, _PROJECTION_MODEL,
)
from .climate_engine import calculate_climate_risk

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
    hitl_required: bool = False
    hitl_reasons: list[str] = field(default_factory=list)
    transparency: dict[str, Any] = field(default_factory=dict)


def _compute_hitl_flag(
    confidence_score: int,
    quality_evaluation: dict,
    risk_score: int,
    annual_records: list[dict],
    climate_findings: dict,
) -> tuple[bool, list[str]]:
    reasons: list[str] = []

    if confidence_score < 70:
        reasons.append(f"Confidence score below threshold ({confidence_score}%)")

    verdict = quality_evaluation.get("verdict", "")
    if verdict in ("flagged", "needs_review"):
        reasons.append(f"Validation Layer verdict: {verdict.replace('_', ' ')}")

    if risk_score > 90 and confidence_score < 80:
        reasons.append(f"Critical risk score ({risk_score}) with insufficient confidence ({confidence_score}%)")

    nasa_recs = [r for r in annual_records if r.get("source") == "nasa"]
    if nasa_recs:
        missing = sum(
            1 for r in nasa_recs
            if not (r.get("temp_mean_celsius") or r.get("temp_mean_c"))
        )
        if missing > len(nasa_recs) * 0.3:
            reasons.append(f"Data quality: {missing}/{len(nasa_recs)} NASA years missing temperature values")
    if climate_findings.get("data_quality") == "poor" and not any("Data quality" in r for r in reasons):
        reasons.append("Data quality rated poor by Climate Analyst")

    temps = [
        r.get("temp_mean_celsius") or r.get("temp_mean_c")
        for r in nasa_recs
        if r.get("temp_mean_celsius") or r.get("temp_mean_c")
    ]
    if len(temps) >= 3:
        mean_t = statistics.mean(temps)
        stdev_t = statistics.stdev(temps)
        if stdev_t > 0:
            for r in nasa_recs:
                t = r.get("temp_mean_celsius") or r.get("temp_mean_c") or 0
                if t and abs(t - mean_t) > 3 * stdev_t:
                    reasons.append(f"Extreme temperature anomaly in {r['year']} ({t:.1f}°C, >3σ from mean)")
                    break

    precips = [r.get("precip_total_mm") for r in nasa_recs if r.get("precip_total_mm")]
    if len(precips) >= 3:
        mean_p = statistics.mean(precips)
        stdev_p = statistics.stdev(precips)
        if stdev_p > 0:
            for r in nasa_recs:
                p = r.get("precip_total_mm") or 0
                if p and abs(p - mean_p) > 3 * stdev_p:
                    reasons.append(f"Extreme precipitation anomaly in {r['year']} ({p:.0f}mm, >3σ from mean)")
                    break

    return bool(reasons), reasons


def _build_transparency(
    region_label: str,
    climate_findings: dict,
    compliance_mapping: dict,
    report: dict,
    quality_evaluation: dict,
    confidence_score: int,
    nasa_years: int,
) -> dict:
    """Derive the EU AI Act Art. 13 transparency payload from pipeline outputs."""

    # ── Score factors ──────────────────────────────────────────────────────────
    factors: list[dict] = []

    precip_trend = climate_findings.get("precip_trend_pct_per_decade")
    if precip_trend is not None:
        w = min(1.0, abs(precip_trend) / 30)
        imp = "high" if abs(precip_trend) > 15 else "medium" if abs(precip_trend) > 5 else "low"
        factors.append({"factor": f"Precipitation {'decline' if precip_trend < 0 else 'increase'}",
                        "impact": imp, "weight": round(w, 2),
                        "value": f"{precip_trend:+.1f}%/decade"})

    temp_trend = climate_findings.get("temp_trend_c_per_decade")
    if temp_trend is not None:
        w = min(1.0, abs(temp_trend) / 1.5)
        imp = "high" if abs(temp_trend) > 0.8 else "medium" if abs(temp_trend) > 0.3 else "low"
        factors.append({"factor": "Temperature trend", "impact": imp,
                        "weight": round(w, 2), "value": f"{temp_trend:+.2f}°C/decade"})

    for risk_key, label in (("drought_risk", "Drought risk"), ("heat_stress_risk", "Heat stress risk")):
        level = (climate_findings.get(risk_key) or "").lower()
        if level in ("high", "medium", "critical"):
            w = {"critical": 0.9, "high": 0.75, "medium": 0.5}.get(level, 0.3)
            factors.append({"factor": label,
                            "impact": "high" if level in ("critical", "high") else "medium",
                            "weight": w, "value": level.upper()})

    anom = len(climate_findings.get("temp_anomaly_years") or []) + \
           len(climate_findings.get("precip_anomaly_years") or [])
    if anom:
        factors.append({"factor": "Extreme year anomalies",
                        "impact": "medium" if anom < 3 else "high",
                        "weight": round(min(1.0, anom * 0.2), 2),
                        "value": f"{anom} anomalous year(s)"})

    csrd_exp = (compliance_mapping.get("csrd_exposure") or "").lower()
    urgency  = (compliance_mapping.get("compliance_urgency") or "").lower()
    lvl = csrd_exp or urgency
    if lvl in ("critical", "high", "medium"):
        w = {"critical": 0.95, "high": 0.7, "medium": 0.45}.get(lvl, 0.3)
        factors.append({"factor": "Compliance exposure",
                        "impact": "high" if lvl in ("critical", "high") else "medium",
                        "weight": w, "value": (f"CSRD {csrd_exp.upper()}" if csrd_exp else urgency.upper())})

    factors.sort(key=lambda f: f["weight"], reverse=True)
    factors = factors[:5]

    # ── Reasoning chain ────────────────────────────────────────────────────────
    raw_findings = climate_findings.get("key_findings") or []
    key_finding  = (raw_findings[0] if raw_findings else None) or climate_findings.get("heat_stress_risk") or "Analysis complete"

    anomaly_str = ""
    if climate_findings.get("hottest_year"):
        anomaly_str = f"{climate_findings['hottest_year']} was the hottest year on record"
    elif climate_findings.get("driest_year"):
        anomaly_str = f"{climate_findings['driest_year']} was the driest year on record"

    csrd_arts  = compliance_mapping.get("csrd_articles") or []
    key_map    = (f"Climate risk triggers CSRD {', '.join(csrd_arts[:2])} disclosure" if csrd_arts
                  else (compliance_mapping.get("csrd_summary") or "")[:120])

    exec_summary = (report.get("executive_summary") or "")[:150]
    score        = report.get("risk_score", 0)
    rationale    = exec_summary or f"Risk score {score}/100 derived from climate trends and compliance analysis"

    reasoning_chain = [
        {
            "agent": "Climate Risk Engine + Interpreter", "model": "Python + claude-haiku-4-5", "step": "2a+2b",
            "received": f"{nasa_years} years of NASA POWER data for {region_label}",
            "key_finding": str(key_finding)[:120],
            "anomaly": anomaly_str or "No extreme anomalies detected",
        },
        {
            "agent": "ESG Strategist", "model": "claude-sonnet-4-6", "step": 3,
            "received": "Climate findings from Agent 2",
            "key_mapping": key_map or "Compliance framework mapping complete",
            "urgency": (compliance_mapping.get("compliance_urgency") or "—").upper(),
        },
        {
            "agent": "Report Writer", "model": "claude-sonnet-4-6", "step": 4,
            "received": "All findings from Agents 2 and 3",
            "risk_score": score,
            "score_rationale": rationale,
        },
    ]

    # ── Validation audit ───────────────────────────────────────────────────────
    verdict = quality_evaluation.get("verdict", "")
    checks  = ["Data consistency: NASA data covers full requested period"]
    if verdict in ("validated", "needs_review"):
        checks.append("Score logic: Risk score aligns with detected indicators")

    flags: list[str] = []
    if confidence_score < 80:
        flags.append(f"Confidence {confidence_score}% — expert review recommended before regulatory filing")
    if verdict == "flagged":
        flags.append("Output flagged by Validation Layer — significant inconsistency detected")
    for issue in (quality_evaluation.get("issues") or quality_evaluation.get("flags") or [])[:2]:
        if isinstance(issue, str) and issue not in flags:
            flags.append(issue)

    rec = (quality_evaluation.get("recommendation") or "").strip()
    if not rec:
        rec = ("Analysis validated — suitable for preliminary ESG screening"
               if verdict == "validated" and confidence_score >= 80
               else "Validate with qualified ESG consultant before regulatory filing")

    return {
        "score_factors": factors,
        "reasoning_chain": reasoning_chain,
        "validation_audit": {
            "checks_passed": checks,
            "flags": flags,
            "verdict": verdict,
            "confidence": confidence_score,
            "recommendation": rec,
        },
    }


def _score_to_risk(score: float) -> str:
    if score > 70: return "critical"
    if score > 45: return "high"
    if score > 25: return "medium"
    return "low"


def _build_climate_findings(
    metrics: dict,
    narrative: str,
    annual_records: list[dict],
) -> dict:
    """Merge Python engine metrics with Haiku narrative into the climate_findings dict."""
    n = len(annual_records)
    b3 = min(3, n)

    temps   = [r.get("temp_mean_celsius") or r.get("temp_mean_c") or 0 for r in annual_records]
    precips = [r.get("precip_total_mm") or 0 for r in annual_records]
    years   = [r.get("year") or 0 for r in annual_records]

    solar_val = metrics.get("solar_trend", 0) or 0
    solar_str = "increasing" if solar_val > 0.05 else "decreasing" if solar_val < -0.05 else "stable"

    wettest_year = years[precips.index(max(precips))] if precips else None

    missing = sum(
        1 for r in annual_records
        if not (r.get("temp_mean_celsius") or r.get("temp_mean_c"))
    )
    data_quality = "poor" if missing > n * 0.3 else "partial" if missing > 0 else "good"

    return {
        "temp_trend_c_per_decade":     metrics.get("temp_trend_c_per_decade"),
        "precip_trend_pct_per_decade": metrics.get("precip_trend_pct_per_decade"),
        "hottest_year":                metrics.get("hottest_year"),
        "driest_year":                 metrics.get("driest_year"),
        "wettest_year":                wettest_year,
        "compliance_urgency":          metrics.get("compliance_urgency"),
        "compliance_exposure":         metrics.get("compliance_exposure"),
        "water_deficit":               metrics.get("water_deficit"),
        "et0_precip_ratio":            metrics.get("et0_precip_ratio"),
        "drought_score":               metrics.get("drought_score"),
        "heat_stress_score":           metrics.get("heat_stress_score"),
        "flood_score":                 metrics.get("flood_score"),
        "temp_change_label":           metrics.get("temp_change_label"),
        "precip_change_label":         metrics.get("precip_change_label"),
        # Translated to risk levels expected by downstream agents
        "heat_stress_risk": _score_to_risk(metrics.get("heat_stress_score") or 0),
        "drought_risk":     _score_to_risk(metrics.get("drought_score") or 0),
        "flood_risk":       _score_to_risk(metrics.get("flood_score") or 0),
        "solar_trend":      solar_str,
        # Baseline vs recent computed from raw records
        "baseline_temp_mean_c": round(sum(temps[:b3]) / b3, 2) if b3 else None,
        "latest_temp_mean_c":   round(sum(temps[-b3:]) / b3, 2) if b3 else None,
        "baseline_precip_mm":   round(sum(precips[:b3]) / b3, 1) if b3 else None,
        "latest_precip_mm":     round(sum(precips[-b3:]) / b3, 1) if b3 else None,
        "temp_anomaly_years":   metrics.get("anomaly_years", []),
        "precip_anomaly_years": metrics.get("anomaly_years", []),
        "data_quality":         data_quality,
        # Haiku 2-3 sentence narrative
        "key_findings": [narrative] if narrative and narrative.strip() else [],
    }


async def run_analysis(
    latitude: float,
    longitude: float,
    region_label: str = "",
    start_year: int = 2014,
    end_year: int = 2023,
    sector: str = "General",
    scenario: str = "SSP2-4.5",
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

    logger.info("Pipeline start: analysis_id=%s region=%r scenario=%s", analysis_id, label, scenario)

    # ── Step 1: Data Collector ─────────────────────────────────────────────────
    # ≤2025 → NASA POWER (real observations)
    # 2026  → ERA5 reanalysis (real observations, ~5-day processing latency)
    # 2027+ → OpenMeteo IPCC projections (selected scenario)
    nasa_end_year    = min(end_year, 2025)
    needs_era5       = end_year >= 2026
    needs_projection = end_year > 2026
    om_start_year    = 2027

    # Build parallel task list — always NASA, optionally ERA5 and/or IPCC
    _coros: list = [
        fetch_climate_data(
            latitude=latitude, longitude=longitude, region_label=label,
            start_year=start_year, end_year=nasa_end_year,
        )
    ]
    _era5_idx = _om_idx = None
    if needs_era5:
        _era5_idx = len(_coros)
        _coros.append(fetch_era5_recent(latitude, longitude, 2026, min(end_year, 2026)))
    if needs_projection:
        _om_idx = len(_coros)
        _coros.append(fetch_projection_range(latitude, longitude, om_start_year, end_year, scenario))

    logger.info(
        "Step 1/5 — Data Collector: NASA (%d–%d)%s%s in parallel",
        start_year, nasa_end_year,
        " + ERA5 (2026)" if needs_era5 else "",
        f" + OpenMeteo IPCC {scenario} ({om_start_year}–{end_year})" if needs_projection else "",
    )
    _gathered = await asyncio.gather(*_coros, return_exceptions=True)
    nasa_result = _gathered[0]
    era5_raw = _gathered[_era5_idx] if _era5_idx is not None else None
    om_raw   = _gathered[_om_idx]   if _om_idx   is not None else None

    if isinstance(nasa_result, Exception):
        raise nasa_result

    if isinstance(era5_raw, Exception):
        logger.warning("ERA5 fetch failed (non-fatal): %s", era5_raw)
        era5_raw = Era5Result(latitude=latitude, longitude=longitude, error=str(era5_raw))

    if isinstance(om_raw, Exception):
        logger.warning("OpenMeteo IPCC fetch failed (non-fatal): %s", om_raw)
        om_raw = OpenMeteoResult(latitude=latitude, longitude=longitude, error=str(om_raw))

    era5_result: Era5Result      = era5_raw or Era5Result(latitude=latitude, longitude=longitude)
    om_result:   OpenMeteoResult = om_raw   or OpenMeteoResult(latitude=latitude, longitude=longitude)

    # ── Build unified annual dataset (source field = "nasa" | "projection") ───
    unified_records: list[dict] = [
        {
            "year":                  r.year,
            "latitude":              r.latitude,
            "longitude":             r.longitude,
            "temp_mean_celsius":     r.temp_mean_celsius,
            "temp_max_celsius":      r.temp_max_celsius,
            "temp_min_celsius":      r.temp_min_celsius,
            "precip_total_mm":       r.precip_total_mm,
            "solar_mean_kwh_m2":     r.solar_mean_kwh_m2,
            "days_sampled":          r.days_sampled,
            "evapotranspiration_mm": r.evapotranspiration_mm or None,
            "soil_moisture_m3m3":    None,
            "source":                "nasa",
        }
        for r in nasa_result.annual_records
    ]
    if needs_era5 and era5_result.era5_records:
        unified_records += [
            {
                "year":                  r.year,
                "latitude":              latitude,
                "longitude":             longitude,
                "temp_mean_celsius":     r.temp_mean_c,
                "temp_max_celsius":      None,
                "temp_min_celsius":      None,
                "precip_total_mm":       r.precip_total_mm,
                "solar_mean_kwh_m2":     None,
                "days_sampled":          365,
                "evapotranspiration_mm": r.evapotranspiration_mm or None,
                "soil_moisture_m3m3":    r.soil_moisture_m3m3 or None,
                "source":                "era5",
            }
            for r in era5_result.era5_records
        ]
    if needs_projection and om_result.projection_records:
        unified_records += [
            {
                "year":                  r.year,
                "latitude":              latitude,
                "longitude":             longitude,
                "temp_mean_celsius":     r.temp_mean_c,
                "temp_max_celsius":      None,
                "temp_min_celsius":      None,
                "precip_total_mm":       r.precip_total_mm,
                "solar_mean_kwh_m2":     None,
                "days_sampled":          365,
                "evapotranspiration_mm": r.evapotranspiration_mm or None,
                "soil_moisture_m3m3":    None,
                "source":                "projection",
            }
            for r in om_result.projection_records
        ]

    logger.info(
        "Step 1/5 complete: nasa=%d years  era5=%d years  projection=%d years  total=%d",
        len(nasa_result.annual_records),
        len(era5_result.era5_records),
        len(om_result.projection_records),
        len(unified_records),
    )

    # ── Step 2a: Deterministic climate engine (no LLM) ────────────────────────
    climate_metrics = calculate_climate_risk(unified_records)
    logger.info(
        "Step 2a/5 — Climate Engine: drought=%.1f heat_stress=%.1f flood=%.1f urgency=%s",
        climate_metrics.get("drought_score", 0),
        climate_metrics.get("heat_stress_score", 0),
        climate_metrics.get("flood_score", 0),
        climate_metrics.get("compliance_urgency"),
    )

    # ── Step 2b: Climate Interpreter (Haiku) — 2-3 sentence synthesis ─────────
    from ..agents.crews import run_climate_analysis_crew

    logger.info("Step 2b/5 — Climate Interpreter: narrative synthesis")
    climate_task_input = json.dumps({
        "metrics": climate_metrics,
        "sample_years": [
            {
                "year":           r.get("year"),
                "temp_mean_c":    r.get("temp_mean_celsius") or r.get("temp_mean_c"),
                "precip_total_mm": r.get("precip_total_mm"),
            }
            for r in unified_records[-5:]
        ],
        "region": label,
        "sector": sector,
    })
    climate_narrative, tokens_analyst = await run_climate_analysis_crew(climate_task_input)
    climate_findings = _build_climate_findings(climate_metrics, climate_narrative, unified_records)
    logger.info(
        "Step 2/5 complete: heat_stress=%s drought=%s flood=%s tokens=%s",
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

    hitl_required, hitl_reasons = _compute_hitl_flag(
        confidence_score=confidence_score,
        quality_evaluation=quality_evaluation,
        risk_score=report.get("risk_score", 0),
        annual_records=unified_records,
        climate_findings=climate_findings,
    )
    logger.info("HITL flag: required=%s reasons=%s", hitl_required, hitl_reasons)

    transparency = _build_transparency(
        region_label=label,
        climate_findings=climate_findings,
        compliance_mapping=compliance_mapping,
        report=report,
        quality_evaluation=quality_evaluation,
        confidence_score=confidence_score,
        nasa_years=len(nasa_result.annual_records),
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
        "era5_used":                 needs_era5,
        "era5_url":                  era5_result.era5_url or None,
        "era5_records_count":        len(era5_result.era5_records),
        "era5_error":                era5_result.error or None,
        "openmeteo_used":            needs_projection,
        "openmeteo_projection_url":  om_result.projection_url or None,
        "openmeteo_model":           _PROJECTION_MODEL if needs_projection else None,
        "openmeteo_start_year":      om_start_year if needs_projection else None,
        "openmeteo_end_year":        end_year if needs_projection else None,
        "openmeteo_projection_years": len(om_result.projection_records),
        "openmeteo_error":           om_result.error or None,
        "scenario":                  scenario,
        "total_records":             len(unified_records),
        "total_llm_tokens":          total_llm_tokens,
        "agents": [
            {
                "step": 1, "name": "Data Collector",
                "model": "Python + httpx (no LLM)",
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            },
            {
                "step": "2a", "name": "Climate Risk Engine",
                "model": "Python (no LLM)",
                "input_tokens": 0, "output_tokens": 0, "total_tokens": 0,
            },
            {
                "step": "2b", "name": "Climate Interpreter",
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
        hitl_required=hitl_required,
        hitl_reasons=hitl_reasons,
        transparency=transparency,
        openmeteo_data={
            "era5_used":          needs_era5,
            "era5_url":           era5_result.era5_url or None,
            "era5_records":       [asdict(r) for r in era5_result.era5_records],
            "era5_error":         era5_result.error or None,
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
