"""CS FastAPI routes."""

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
from ..pipeline.orchestrator import run_analysis
from .models import AnalysisResponse, AnalysisSummary, AnalyzeRequest, BatchAnalysisResponse, BatchRowResult

logger = logging.getLogger(__name__)

router = APIRouter()


@router.api_route("/health", methods=["GET", "HEAD"])
@limiter.limit("60/minute")
async def health(request: Request) -> dict:
    return {
        "status": "ok",
        "service": "climate-sentinel",
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


_PIPELINE_TIMEOUT_SEC = 180  # 5-agent pipeline; NASA + 4 LLM calls


@router.post("/api/analyze", response_model=AnalysisResponse)
@limiter.limit("10/hour")
async def analyze(
    request: Request,
    body: AnalyzeRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
) -> AnalysisResponse:
    """Run the full 4-agent CS pipeline and persist the result."""
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


_BATCH_MAX_ROWS = 10
_BATCH_MAX_FILE_BYTES = 1_000_000  # 1 MB
_BATCH_REQUIRED_COLS = {"region", "latitude", "longitude"}
_BATCH_TEMPLATE_CSV = (
    "region,latitude,longitude,sector,scenario\n"
    "São Paulo Brazil,-23.5505,-46.6333,General,SSP2-4.5\n"
    "Brasília Brazil,-15.7801,-47.9292,General,SSP2-4.5\n"
    "Berlin Germany,52.5200,13.4050,General,SSP1-2.6\n"
    "Amsterdam Netherlands,52.3676,4.9041,General,SSP1-2.6\n"
    "Lagos Nigeria,6.5244,3.3792,General,SSP5-8.5\n"
    "Mumbai India,19.0760,72.8777,General,SSP2-4.5\n"
    "Sydney Australia,-33.8688,151.2093,General,SSP1-2.6\n"
    "Buenos Aires Argentina,-34.6037,-58.3816,General,SSP2-4.5\n"
    "Helsinki Finland,60.1699,24.9384,General,SSP1-2.6\n"
    "Dubai UAE,25.2048,55.2708,General,SSP5-8.5\n"
)

# In-memory job store for async batch processing.
# Note: single-instance only — use Redis for multi-instance deployments.
_batch_jobs: dict[str, dict] = {}


def _inv_label(score: int) -> str:
    if score <= 40: return "Investment Approved"
    if score <= 70: return "Investment Conditioned"
    if score <= 85: return "Investment Restricted"
    return "Investment Suspended"



@router.post("/api/analyze/batch")
@limiter.limit("3/hour")
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
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="CSV must be UTF-8 encoded")

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
            lat = float(row.get("latitude") or 0)
            lon = float(row.get("longitude") or 0)
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

        if i > 0:
            await asyncio.sleep(2)  # avoid NASA POWER rate limiting

        try:
            result = await asyncio.wait_for(
                run_analysis(
                    latitude=lat, longitude=lon, region_label=region,
                    start_year=2014, end_year=2023,
                    sector=sector, scenario=scenario,
                ),
                timeout=120,
            )
            try:
                await save_analysis(result, session_id=session_id)
            except Exception:
                logger.warning("Batch %s: failed to persist %s", job_id, result.analysis_id)

            job["results"].append({
                "region": region, "latitude": lat, "longitude": lon,
                "sector": sector, "scenario": scenario,
                "risk_score": result.risk_score, "risk_level": result.risk_level,
                "investment_status": _inv_label(result.risk_score),
                "confidence_score": result.confidence_score,
                "analysis_id": result.analysis_id,
                "status": "completed", "error": "",
            })
            logger.info("Batch %s row %d/%d done: %r score=%d", job_id, i + 1, job["total"], region, result.risk_score)

        except Exception as exc:
            logger.warning("Batch %s row %d/%d failed: %r error=%s", job_id, i + 1, job["total"], region, exc)
            job["results"].append({
                "region": region, "latitude": lat, "longitude": lon,
                "sector": sector, "scenario": scenario,
                "risk_score": 0, "risk_level": "", "investment_status": "",
                "confidence_score": 0, "analysis_id": "",
                "status": "error", "error": str(exc)[:200],
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
            "Content-Disposition": 'attachment; filename="climate_sentinel_batch.xlsx"',
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
