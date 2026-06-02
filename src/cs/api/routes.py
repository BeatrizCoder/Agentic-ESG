"""CS FastAPI routes."""

import logging
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Header
from fastapi.responses import StreamingResponse

from ..core.config import limiter
from ..db.mongo import delete_analysis as _db_delete
from ..db.mongo import get_analysis as _db_get
from ..db.mongo import get_recent_analyses, get_session_history, save_analysis
from ..pipeline.orchestrator import run_analysis
from .models import AnalysisResponse, AnalysisSummary, AnalyzeRequest

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


@router.post("/api/analyze", response_model=AnalysisResponse)
@limiter.limit("5/minute")
async def analyze(
    request: Request,
    body: AnalyzeRequest,
    x_session_id: str | None = Header(None, alias="X-Session-ID")
) -> AnalysisResponse:
    """Run the full 4-agent CS pipeline and persist the result."""
    if body.end_year <= body.start_year:
        raise HTTPException(status_code=400, detail="end_year must be greater than start_year")

    logger.info(
        "POST /api/analyze: region=%r lat=%.4f lon=%.4f years=%d-%d session_id=%s",
        body.region_label or "(unnamed)",
        body.latitude,
        body.longitude,
        body.start_year,
        body.end_year,
        x_session_id or "none",
    )

    result = await run_analysis(
        latitude=body.latitude,
        longitude=body.longitude,
        region_label=body.region_label,
        start_year=body.start_year,
        end_year=body.end_year,
        sector=body.sector,
        scenario=body.scenario,
    )

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
