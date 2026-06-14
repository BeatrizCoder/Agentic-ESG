"""AESG FastAPI routes."""

import asyncio
import csv
import io
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, File, HTTPException, Request, Header, UploadFile
from fastapi.responses import StreamingResponse

from ..core.config import limiter
from ..db.mongo import delete_analysis as _db_delete
from ..db.mongo import get_analysis as _db_get
from ..db.mongo import get_recent_analyses, get_session_history, save_analysis
from ..pipeline.orchestrator import run_analysis, run_comparison_pipeline
from .models import AnalysisResponse, AnalysisSummary, AnalyzeRequest, BatchAnalysisResponse, BatchRowResult, CompareRequest, ExportWithComparisonRequest

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/sectors")
@limiter.limit("60/minute")
async def list_sectors(request: Request) -> dict:
    """List all available sector profiles for ESG analysis."""
    from ..sectors import list_available_sectors, SECTOR_MAPPING
    
    sectors = list_available_sectors()
    
    return {
        "sectors": sectors,
        "aliases": {
            alias: target for alias, target in SECTOR_MAPPING.items()
        },
        "count": len(sectors),
    }


@router.api_route("/health", methods=["GET", "HEAD"])
@limiter.limit("60/minute")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": "agentic-esg",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


_PIPELINE_TIMEOUT_SEC = 300  # 5-agent pipeline; NASA + 4 LLM calls (projection analyses can take ~3 min)


@router.post("/api/analyze", response_model=AnalysisResponse)
@limiter.limit("3/week")
async def analyze(
    request: Request,
    body: AnalyzeRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
) -> AnalysisResponse:
    """Run the full 4-agent AESG pipeline and persist the result."""
    logger.info(
        "POST /api/analyze: region=%r lat=%.4f lon=%.4f years=%d-%d session_id=%s",
        body.region_label or "(unnamed)",
        body.latitude,
        body.longitude,
        body.start_year,
        body.end_year,
        x_session_id or "none",
    )

    try:
        result = await asyncio.wait_for(
            run_analysis(
                latitude=body.latitude,
                longitude=body.longitude,
                region_label=body.region_label,
                start_year=body.start_year,
                end_year=body.end_year,
                sector=body.sector,
                scenario=body.scenario,
            ),
            timeout=_PIPELINE_TIMEOUT_SEC,
        )
    except asyncio.TimeoutError:
        logger.error(
            "Pipeline timeout after %ds: region=%r lat=%.4f lon=%.4f",
            _PIPELINE_TIMEOUT_SEC,
            body.region_label or "(unnamed)",
            body.latitude,
            body.longitude,
        )
        raise HTTPException(
            status_code=504,
            detail=f"Analysis timed out after {_PIPELINE_TIMEOUT_SEC}s. Please try again.",
        )
    except ValueError as exc:
        logger.warning("Pipeline input error: %s", exc)
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        logger.exception(
            "Pipeline failed: region=%r lat=%.4f lon=%.4f",
            body.region_label or "(unnamed)",
            body.latitude,
            body.longitude,
        )
        raise HTTPException(status_code=500, detail="Analysis pipeline failed. Please try again.")

    try:
        await save_analysis(result, session_id=x_session_id)
    except Exception:
        logger.exception("Failed to persist analysis %s", result.analysis_id)

    return AnalysisResponse(
        analysis_id=result.analysis_id,
        region_label=result.region_label,
        latitude=result.latitude,
        longitude=result.longitude,
        risk_score=result.risk_score,
        risk_level=result.risk_level,
        risk_badge_label=result.risk_badge_label,
        executive_summary=result.executive_summary,
        recommendations=result.recommendations,
        key_metrics=result.key_metrics,
        climate_findings=result.climate_findings,
        compliance_mapping=result.compliance_mapping,
        annual_records=result.annual_records,
        pipeline_metadata=result.pipeline_metadata,
        confidence_score=result.confidence_score,
        quality_evaluation=result.quality_evaluation,
        openmeteo_data=result.openmeteo_data,
        offset_targets=result.offset_targets,
        sector=result.sector,
        scenario=result.scenario,
        pipeline_duration_sec=result.pipeline_duration_sec,
        created_at=result.created_at,
        error=result.error,
        hitl_required=result.hitl_required,
        hitl_reasons=result.hitl_reasons,
        transparency=result.transparency,
    )


@router.get("/api/analyses", response_model=list[AnalysisSummary])
@limiter.limit("30/minute")
async def list_analyses(request: Request) -> list[AnalysisSummary]:
    """Return the 50 most recent analyses (summary only, no heavy payloads)."""
    rows = await get_recent_analyses(limit=50)
    return [
        AnalysisSummary(
            analysis_id=r["analysis_id"],
            region_label=r["region_label"],
            latitude=r["latitude"],
            longitude=r["longitude"],
            risk_score=r["risk_score"],
            risk_level=r["risk_level"],
            risk_badge_label=r["risk_badge_label"],
            created_at=r["created_at"],
            pipeline_duration_sec=r["pipeline_duration_sec"],
        )
        for r in rows
    ]


@router.get("/api/analyses/history", response_model=list[AnalysisSummary])
@limiter.limit("30/minute")
async def get_history(
    request: Request,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
) -> list[AnalysisSummary]:
    """Return the most recent analyses for the current session (last 10)."""
    if not x_session_id:
        raise HTTPException(status_code=400, detail="X-Session-ID header required")
    
    rows = await get_session_history(x_session_id, limit=10)
    items = []
    for r in rows:
        try:
            items.append(AnalysisSummary(
                analysis_id=r.get("analysis_id", ""),
                region_label=r.get("region_label", r.get("region", "Unknown")),
                latitude=float(r.get("latitude", 0)),
                longitude=float(r.get("longitude", 0)),
                risk_score=int(r.get("risk_score", 0)),
                risk_level=r.get("risk_level", ""),
                risk_badge_label=r.get("risk_badge_label", r.get("risk_level", "")),
                created_at=r.get("created_at", ""),
                pipeline_duration_sec=float(r.get("pipeline_duration_sec", 0)),
            ))
        except Exception as exc:
            logger.warning("Skipping malformed history doc %s: %s", r.get("analysis_id", "?"), exc)
    return items


@router.get("/api/analyses/{analysis_id}", response_model=AnalysisResponse)
@limiter.limit("30/minute")
async def get_analysis(request: Request, analysis_id: str) -> AnalysisResponse:
    """Return the full payload for a single analysis."""
    row = await _db_get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")
    return AnalysisResponse(**row)


@router.delete("/api/analyses/{analysis_id}")
@limiter.limit("10/minute")
async def delete_analysis(request: Request, analysis_id: str) -> dict:
    if not await _db_delete(analysis_id):
        raise HTTPException(status_code=404, detail="Analysis not found")
    return {"deleted": analysis_id}


@router.get("/api/analyses/{analysis_id}/export/pdf")
@limiter.limit("5/minute")
async def export_pdf(request: Request, analysis_id: str) -> StreamingResponse:
    """Generate and stream a PDF report for the given analysis."""
    row = await _db_get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")

    try:
        from ..exports.pdf_report import generate_pdf
        buffer = generate_pdf(row)
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF export not available — install reportlab")
    except Exception as exc:
        logger.exception("PDF generation failed for %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"cs_report_{analysis_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/api/analyses/{analysis_id}/export/pdf")
@limiter.limit("5/minute")
async def export_pdf_with_comparison(
    request: Request,
    analysis_id: str,
    body: ExportWithComparisonRequest,
) -> StreamingResponse:
    """Generate a PDF report optionally including a historical comparison section."""
    row = await _db_get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")

    try:
        from ..exports.pdf_report import generate_pdf
        buffer = generate_pdf(row, comparison_data=body.comparison_data)
    except ImportError:
        raise HTTPException(status_code=503, detail="PDF export not available — install reportlab")
    except Exception as exc:
        logger.exception("PDF generation failed for %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {exc}")

    filename = f"cs_report_{analysis_id}.pdf"
    return StreamingResponse(
        buffer,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )


_BATCH_MAX_ROWS = 5
_BATCH_MAX_FILE_BYTES = 1_000_000  # 1 MB
_BATCH_REQUIRED_COLS = {"region", "latitude", "longitude"}
_BATCH_TEMPLATE_CSV = (
    "region,latitude,longitude,start_year,end_year,compare_start_year,compare_end_year,sector,scenario\n"
    "São Paulo Brazil,-23.5505,-46.6333,2014,2025,,,General,SSP2-4.5\n"
    "Brasília Brazil,-15.7801,-47.9292,2014,2025,,,General,SSP2-4.5\n"
    "Berlin Germany,52.5200,13.4050,2014,2025,,,General,SSP1-2.6\n"
    "Amsterdam Netherlands,52.3676,4.9041,2014,2025,,,General,SSP1-2.6\n"
    "Lagos Nigeria,6.5244,3.3792,2014,2025,,,General,SSP5-8.5\n"
    "Mumbai India,19.0760,72.8777,2014,2025,,,General,SSP2-4.5\n"
    "Sydney Australia,-33.8688,151.2093,2014,2025,,,General,SSP1-2.6\n"
    "Buenos Aires Argentina,-34.6037,-58.3816,2014,2025,,,General,SSP2-4.5\n"
    "Helsinki Finland,60.1699,24.9384,2014,2025,,,General,SSP1-2.6\n"
    "Dubai UAE,25.2048,55.2708,2014,2025,,,General,SSP5-8.5\n"
)

# In-memory job store for async batch processing.
# Note: single-instance only — use Redis for multi-instance deployments.
_batch_jobs: dict[str, dict] = {}


def _inv_label(score: int) -> str:
    if score <= 40: return "Investment Approved"
    if score <= 70: return "Investment Conditioned"
    if score <= 85: return "Investment Restricted"
    return "Investment Suspended"



def _extract_comparison_score(result: dict) -> int | None:
    """Return risk_score, or a composite fallback if score is 0."""
    score = result.get("risk_score") or 0
    if score > 0:
        return score
    drought = result.get("drought_score") or 0
    heat    = result.get("heat_stress_score") or 0
    if drought > 0 or heat > 0:
        return min(100, int(drought * 0.6 + heat * 0.4))
    return None


def _safe_extract_period(result: dict, label: str) -> dict:
    """Return a sanitized flat period dict — fills missing keys with safe defaults."""
    return {
        "label":         result.get("label") or label,
        "risk_score":    result.get("risk_score") or 0,
        "risk_level":    result.get("risk_level") or "",
        "temp_mean":     result.get("temp_mean") or 0.0,
        "temp_trend":    result.get("temp_trend") or 0.0,
        "precip_trend":  result.get("precip_trend"),
        "drought_score": result.get("drought_score") or 0,
        "flood_score":   result.get("flood_score") or 0,
        "heat_score":    result.get("heat_stress_score") or 0,
        "key_finding":   result.get("key_finding") or "",
        "record_count":  result.get("record_count") or 0,
    }


@router.post("/api/analyze/compare")
@limiter.limit("2/week")
async def compare_periods(request: Request, body: CompareRequest) -> dict:
    """Lightweight dual-period comparison: Data Collector + Climate Engine + Haiku only."""
    from ..pipeline.orchestrator import run_comparison_pipeline

    logger.info(
        "compare_periods start: region=%r lat=%.4f lon=%.4f "
        "period_1=%d-%d period_2=%d-%d sector=%r",
        body.region_label, body.latitude, body.longitude,
        body.period_1.start_year, body.period_1.end_year,
        body.period_2.start_year, body.period_2.end_year,
        body.sector,
    )
    try:
        # Run historical period (period_2) first so its temp_mean can serve as
        # the fixed reference baseline for scoring period_1 (recent).
        logger.info("compare_periods: starting period_2 pipeline (%d-%d)",
                    body.period_2.start_year, body.period_2.end_year)
        p2 = await asyncio.wait_for(
            run_comparison_pipeline(
                latitude=body.latitude, longitude=body.longitude,
                region_label=body.region_label, sector=body.sector,
                start_year=body.period_2.start_year, end_year=body.period_2.end_year,
            ),
            timeout=90,
        )
        logger.info("compare_periods: period_2 done — score=%s temp_mean=%s records=%s",
                    p2.get("risk_score"), p2.get("temp_mean"), p2.get("record_count"))
        await asyncio.sleep(2)
        logger.info("compare_periods: starting period_1 pipeline (%d-%d)",
                    body.period_1.start_year, body.period_1.end_year)
        p1 = await asyncio.wait_for(
            run_comparison_pipeline(
                latitude=body.latitude, longitude=body.longitude,
                region_label=body.region_label, sector=body.sector,
                start_year=body.period_1.start_year, end_year=body.period_1.end_year,
                reference_temp_mean=p2.get("temp_mean"),
            ),
            timeout=90,
        )
        logger.info("compare_periods: period_1 done — score=%s temp_mean=%s records=%s",
                    p1.get("risk_score"), p1.get("temp_mean"), p1.get("record_count"))
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Comparison timed out. Please try again.")
    except Exception as exc:
        logger.exception("compare_periods FAILED: %s: %s", type(exc).__name__, exc)
        raise HTTPException(status_code=500, detail=f"Comparison failed: {type(exc).__name__}: {exc}")

    logger.info("compare_periods period_1 raw: %s", p1)
    logger.info("compare_periods period_2 raw: %s", p2)

    p1["risk_score"] = _extract_comparison_score(p1)
    p2["risk_score"] = _extract_comparison_score(p2)

    logger.info("compare_periods scores after extract: p1=%s p2=%s", p1["risk_score"], p2["risk_score"])

    s1 = p1["risk_score"] or 0
    s2 = p2["risk_score"] or 0

    if s1 < s2:
        logger.warning(
            "Comparison scores seem inverted: recent=%d < historical=%d for %r",
            s1, s2, body.region_label,
        )
    score_delta  = s1 - s2
    temp_delta   = round((p1["temp_mean"] or 0) - (p2["temp_mean"] or 0), 2)
    trend_delta  = round((p1["temp_trend"] or 0) - (p2["temp_trend"] or 0), 3)
    p1_pt        = p1["precip_trend"]
    p2_pt        = p2["precip_trend"]
    precip_delta = round(p1_pt - p2_pt, 1) if p1_pt is not None and p2_pt is not None else None
    drought_delta = round((p1["drought_score"] or 0) - (p2["drought_score"] or 0), 1)

    if score_delta > 20:
        interp = f"Risk increased significantly from {p2['label']} to {p1['label']} (+{score_delta} pts). {p1.get('key_finding', '')}".strip()
    elif score_delta > 5:
        interp = f"Risk increased moderately from {p2['label']} to {p1['label']} (+{score_delta} pts). {p1.get('key_finding', '')}".strip()
    elif score_delta < -5:
        interp = f"Risk decreased from {p2['label']} to {p1['label']} ({score_delta} pts). {p1.get('key_finding', '')}".strip()
    else:
        interp = f"Risk remained stable between {p2['label']} and {p1['label']}. {p1.get('key_finding', '')}".strip()

    return {
        "region_label": body.region_label,
        "period_1": p1,
        "period_2": p2,
        "delta": {
            "risk_score":    score_delta,
            "temp_mean":     temp_delta,
            "temp_trend":    trend_delta,
            "precip_trend":  precip_delta,
            "drought_score": drought_delta,
            "interpretation": interp,
        },
        "comparison_note": (
            "Scores calculated independently per period against each period's own baseline. "
            "Higher score = higher risk relative to that period. "
            "Use delta values for trend analysis."
        ),
    }


@router.post("/api/analyze/batch")
@limiter.limit("1/week")
async def start_batch(
    request: Request,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_session_id: str | None = Header(None, alias="X-Session-ID"),
) -> dict:
    """Start an async batch job. Returns job_id for polling."""
    content = await file.read()
    if len(content) > _BATCH_MAX_FILE_BYTES:
        raise HTTPException(status_code=413, detail="File too large. Maximum 1 MB.")
    for encoding in ["utf-8-sig", "utf-8", "latin-1", "cp1252"]:
        try:
            text = content.decode(encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise HTTPException(status_code=400, detail="CSV encoding not supported. Save as UTF-8 and try again.")

    reader = csv.DictReader(io.StringIO(text))
    try:
        rows = list(reader)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {exc}")

    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty")

    fieldnames = set(rows[0].keys())
    missing = _BATCH_REQUIRED_COLS - fieldnames
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(missing))}. Required: region, latitude, longitude",
        )

    if len(rows) > _BATCH_MAX_ROWS:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Maximum {_BATCH_MAX_ROWS} regions per batch. "
                f"Your CSV has {len(rows)} rows. "
                f"Please reduce to {_BATCH_MAX_ROWS} or fewer and try again. "
                f"/ Máximo {_BATCH_MAX_ROWS} regiões por lote. Seu CSV tem {len(rows)} linhas."
            ),
        )

    job_id = str(uuid.uuid4())
    _batch_jobs[job_id] = {
        "status": "running",
        "total": len(rows),
        "completed": 0,
        "failed": 0,
        "results": [],
    }

    background_tasks.add_task(_process_batch, job_id, rows, x_session_id)
    logger.info("Batch job %s started: %d rows", job_id, len(rows))
    return {"job_id": job_id, "total": len(rows)}


async def _process_batch(job_id: str, rows: list, session_id: str | None) -> None:
    job = _batch_jobs[job_id]
    for i, row in enumerate(rows):
        region   = (row.get("region") or "").strip()
        sector   = (row.get("sector") or "General").strip() or "General"
        scenario = (row.get("scenario") or "SSP2-4.5").strip()
        if scenario not in ("SSP1-2.6", "SSP2-4.5", "SSP5-8.5"):
            scenario = "SSP2-4.5"

        try:
            lat        = float(row.get("latitude") or 0)
            lon        = float(row.get("longitude") or 0)
            start_year = int(row.get("start_year") or 2014)
            end_year   = int(row.get("end_year")   or 2025)
        except (ValueError, TypeError):
            job["results"].append({
                "region": region, "latitude": 0.0, "longitude": 0.0,
                "sector": sector, "scenario": scenario,
                "risk_score": 0, "risk_level": "", "investment_status": "",
                "confidence_score": 0, "analysis_id": "",
                "status": "error", "error": "Invalid latitude or longitude value",
            })
            job["failed"] += 1
            job["completed"] = i + 1
            continue

        compare_start = (row.get("compare_start_year") or "").strip()
        compare_end   = (row.get("compare_end_year") or "").strip()
        compare_mode = False
        compare_start_year = None
        compare_end_year = None
        if compare_start and compare_end:
            try:
                compare_start_year = int(compare_start)
                compare_end_year = int(compare_end)
                if compare_end_year > compare_start_year:
                    compare_mode = True
            except (ValueError, TypeError):
                compare_mode = False

        if i > 0:
            await asyncio.sleep(2)  # avoid NASA POWER rate limiting

        try:
            if compare_mode:
                p1 = await asyncio.wait_for(
                    run_comparison_pipeline(
                        latitude=lat, longitude=lon, region_label=region,
                        sector=sector,
                        start_year=compare_start_year, end_year=compare_end_year,
                    ),
                    timeout=180,
                )
                await asyncio.sleep(2)
                p2 = await asyncio.wait_for(
                    run_comparison_pipeline(
                        latitude=lat, longitude=lon, region_label=region,
                        sector=sector,
                        start_year=start_year, end_year=end_year,
                    ),
                    timeout=180,
                )
                p1["risk_score"] = _extract_comparison_score(p1) or 0
                p2["risk_score"] = _extract_comparison_score(p2) or 0
                s1 = p1["risk_score"]
                s2 = p2["risk_score"]
                delta = {
                    "risk_score": s1 - s2,
                    "temp_mean": round((p1.get("temp_mean") or 0) - (p2.get("temp_mean") or 0), 2),
                    "temp_trend": round((p1.get("temp_trend") or 0) - (p2.get("temp_trend") or 0), 3),
                    "precip_trend": (
                        round((p1.get("precip_trend") or 0) - (p2.get("precip_trend") or 0), 1)
                        if p1.get("precip_trend") is not None and p2.get("precip_trend") is not None
                        else None
                    ),
                    "drought_score": round((p1.get("drought_score") or 0) - (p2.get("drought_score") or 0), 1),
                }
                result = {"period_1": p1, "period_2": p2, "delta": delta}
            else:
                result = await asyncio.wait_for(
                    run_analysis(
                        latitude=lat, longitude=lon, region_label=region,
                        start_year=start_year, end_year=end_year,
                        sector=sector, scenario=scenario,
                    ),
                    timeout=180,
                )

            if compare_mode:
                p2 = result.get("period_2", {})
                risk_score = p2.get("risk_score", 0) or 0
                risk_level = p2.get("risk_level", "")
                investment_status = _inv_label(risk_score)
                job["results"].append({
                    "region": region, "latitude": lat, "longitude": lon,
                    "sector": sector, "scenario": scenario,
                    "risk_score": risk_score, "risk_level": risk_level,
                    "investment_status": investment_status,
                    "confidence_score": 0,
                    "analysis_id": "",
                    "comparison_mode": True,
                    "period_1": result.get("period_1"),
                    "period_2": result.get("period_2"),
                    "delta": result.get("delta"),
                    "status": "completed", "error": "",
                })
                logger.info("Batch %s row %d/%d done: %r comparison mode", job_id, i + 1, job["total"], region)
            else:
                logger.info(f"Saving batch analysis for session: {session_id}")
                try:
                    await save_analysis(result, session_id=session_id, source="batch")
                    logger.info("Batch analysis saved to history: %s (session=%s)", result.analysis_id, session_id)
                except Exception as save_exc:
                    logger.warning("Batch save error: %s (analysis=%s session=%s)", save_exc, result.analysis_id, session_id)

                job["results"].append({
                    "region": region, "latitude": lat, "longitude": lon,
                    "sector": sector, "scenario": scenario,
                    "risk_score": result.risk_score, "risk_level": result.risk_level,
                    "investment_status": _inv_label(result.risk_score),
                    "confidence_score": result.confidence_score,
                    "analysis_id": result.analysis_id,
                    "comparison_mode": False,
                    "period_1": None,
                    "period_2": None,
                    "delta": None,
                    "status": "completed", "error": "",
                })
                logger.info("Batch %s row %d/%d done: %r score=%d", job_id, i + 1, job["total"], region, result.risk_score)

        except asyncio.TimeoutError:
            err_msg = "Pipeline timed out after 120s — NASA API may be slow, please retry"
            logger.warning("Batch %s row %d/%d TIMEOUT: %r", job_id, i + 1, job["total"], region)
            job["results"].append({
                "region": region, "latitude": lat, "longitude": lon,
                "sector": sector, "scenario": scenario,
                "risk_score": 0, "risk_level": "", "investment_status": "",
                "confidence_score": 0, "analysis_id": "",
                "comparison_mode": False,
                "period_1": None, "period_2": None, "delta": None,
                "status": "error", "error": err_msg,
            })
            job["failed"] += 1
        except Exception as exc:
            err_msg = str(exc) or f"{type(exc).__name__} (no message)"
            logger.warning(
                "Batch %s row %d/%d failed: %r — %s: %s",
                job_id, i + 1, job["total"], region, type(exc).__name__, err_msg,
                exc_info=True,
            )
            job["results"].append({
                "region": region, "latitude": lat, "longitude": lon,
                "sector": sector, "scenario": scenario,
                "risk_score": 0, "risk_level": "", "investment_status": "",
                "confidence_score": 0, "analysis_id": "",
                "comparison_mode": False,
                "period_1": None, "period_2": None, "delta": None,
                "status": "error", "error": f"{type(exc).__name__}: {err_msg}"[:300],
            })
            job["failed"] += 1

        job["completed"] = i + 1

    job["status"] = "completed"
    logger.info("Batch job %s completed: %d/%d", job_id, job["completed"] - job["failed"], job["total"])


@router.get("/api/analyze/batch/{job_id}")
@limiter.limit("60/minute")
async def get_batch_status(request: Request, job_id: str) -> dict:
    """Poll status of an async batch job."""
    job = _batch_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found or expired")
    return job


@router.post("/api/batch/export/excel")
@limiter.limit("10/minute")
async def batch_export_excel(
    request: Request,
    body: BatchAnalysisResponse,
) -> StreamingResponse:
    """Generate an Excel summary for batch results."""
    try:
        from ..exports.excel_report import generate_batch_excel
        buffer = generate_batch_excel(body.model_dump())
    except ImportError:
        raise HTTPException(status_code=503, detail="Excel export not available — install openpyxl")
    except Exception as exc:
        logger.exception("Batch Excel generation failed")
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {exc}")

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="agentic_esg_batch.xlsx"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )


@router.get("/api/analyses/{analysis_id}/export/excel")
@limiter.limit("5/minute")
async def export_excel(request: Request, analysis_id: str) -> StreamingResponse:
    """Generate and stream an Excel report for the given analysis."""
    row = await _db_get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")

    try:
        from ..exports.excel_report import generate_excel
        buffer = generate_excel(row)
    except ImportError:
        raise HTTPException(status_code=503, detail="Excel export not available — install openpyxl")
    except Exception as exc:
        logger.exception("Excel generation failed for %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {exc}")

    filename = f"cs_report_{analysis_id}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )


@router.post("/api/analyses/{analysis_id}/export/excel")
@limiter.limit("5/minute")
async def export_excel_with_comparison(
    request: Request,
    analysis_id: str,
    body: ExportWithComparisonRequest,
) -> StreamingResponse:
    """Generate an Excel report optionally including a historical comparison sheet."""
    row = await _db_get(analysis_id)
    if not row:
        raise HTTPException(status_code=404, detail=f"Analysis '{analysis_id}' not found")

    try:
        from ..exports.excel_report import generate_excel
        buffer = generate_excel(row, comparison_data=body.comparison_data)
    except ImportError:
        raise HTTPException(status_code=503, detail="Excel export not available — install openpyxl")
    except Exception as exc:
        logger.exception("Excel generation failed for %s", analysis_id)
        raise HTTPException(status_code=500, detail=f"Excel generation failed: {exc}")

    filename = f"cs_report_{analysis_id}.xlsx"
    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
            "Cache-Control": "no-cache",
        },
    )
