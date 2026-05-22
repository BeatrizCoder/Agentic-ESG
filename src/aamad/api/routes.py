"""FastAPI routes for the AAMAD support platform."""

import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import text as sa_text

from pydantic import BaseModel

from ..config import ENABLE_MOCK_INTEGRATIONS
from ..core.config import verify_api_key, limiter, JWT_EXPIRE_HOURS
from ..core import services as _svc
from ..data_store import data_store, SupportTicketData, SupportTicketDB
from ..flow.support_flow import SupportFlow
from ..auth import create_guest_token, verify_token
from .models import (
    FeedbackRequest, RunMetrics, StatusResponse,
    StepsResponse, SupportResponse, SupportTicket, TraceResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Auth models ───────────────────────────────────────────────────────────────

class GuestLoginRequest(BaseModel):
    accepted_terms: bool
    accepted_privacy: bool


# ── Auth endpoints ────────────────────────────────────────────────────────────

@router.post("/auth/guest")
async def guest_login(request: GuestLoginRequest):
    if not request.accepted_terms:
        raise HTTPException(status_code=400, detail="Must accept Terms of Service")
    if not request.accepted_privacy:
        raise HTTPException(status_code=400, detail="Must accept Privacy Policy")
    token = create_guest_token()
    logger.info("Guest token issued")
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": JWT_EXPIRE_HOURS * 3600,
        "user": {"name": "Demo User", "role": "guest", "email": "guest@demo.com"},
    }


@router.get("/auth/me")
async def get_me(user=Depends(verify_token)):
    return {
        "name": user.get("name", "Demo User"),
        "role": user.get("role", "guest"),
        "email": user.get("sub"),
    }


# ── Dataset helpers ───────────────────────────────────────────────────────────

def _get_demo_tickets() -> List[SupportTicketData]:
    """Read tickets from demo_dataset.db without touching the live database."""
    import json as _json
    from sqlalchemy import create_engine, text as _text
    from pathlib import Path as _Path

    demo_db = _Path("src/aamad/data/demo_dataset.db")
    if not demo_db.exists():
        return []
    try:
        engine = create_engine(f"sqlite:///{demo_db}")
        with engine.connect() as conn:
            rows = conn.execute(
                _text("SELECT * FROM support_tickets ORDER BY created_at DESC")
            ).mappings().all()
        result = []
        for r in rows:
            r = dict(r)

            def _j(key, default="[]"):
                raw = r.get(key) or default
                try:
                    return _json.loads(raw) if isinstance(raw, str) else (raw or _json.loads(default))
                except Exception:
                    return _json.loads(default)

            result.append(SupportTicketData(
                reference_id=r.get("reference_id", ""),
                run_id=r.get("run_id", ""),
                inquiry=r.get("inquiry", ""),
                category=r.get("category", ""),
                category_confidence=r.get("category_confidence") or 0,
                sentiment=r.get("sentiment", ""),
                sentiment_confidence=r.get("sentiment_confidence") or 0,
                urgency=r.get("urgency", ""),
                articles=_j("articles"),
                escalation_required=bool(r.get("escalation_required", False)),
                escalation_reason=r.get("escalation_reason", ""),
                triggered_keyword=r.get("triggered_keyword"),
                response=r.get("response", ""),
                response_confidence=r.get("response_confidence") or 0,
                quality_evaluation=_j("quality_evaluation", "{}"),
                steps=_j("steps"),
                tools_used=_j("tools_used"),
                api_tags=_j("api_tags"),
                execution_time_ms=r.get("execution_time_ms") or 0,
                created_at=r.get("created_at", ""),
                updated_at=r.get("updated_at") or r.get("created_at", ""),
                pending_action=_j("pending_action", "{}"),
                knowledge_source=r.get("knowledge_source", ""),
                memory_saved=bool(r.get("memory_saved", False)),
                execution_mode=r.get("execution_mode", ""),
                cache_used=bool(r.get("cache_used", False)),
            ))
        return result
    except Exception as _e:
        logger.error(f"Error reading demo dataset: {_e}")
        return []


def _get_ticket_count(mode: str) -> int:
    """Get ticket count for a given mode without side effects."""
    from sqlalchemy import create_engine, text as _text
    from pathlib import Path as _Path

    try:
        if mode == "historical":
            demo_db = _Path("src/aamad/data/demo_dataset.db")
            if not demo_db.exists():
                return 0
            engine = create_engine(f"sqlite:///{demo_db}")
            with engine.connect() as conn:
                return conn.execute(
                    _text("SELECT COUNT(*) FROM support_tickets")
                ).scalar() or 0
        else:
            with data_store.SessionLocal() as session:
                return session.execute(
                    _text("SELECT COUNT(*) FROM support_tickets")
                ).scalar() or 0
    except Exception:
        return 0


def _get_historical_csat_metrics() -> Dict[str, Any]:
    """Calculate CSAT from the demo SQLite DB, handling JSON-dict and plain-string feedback."""
    import json as _json
    from sqlalchemy import create_engine, text as _text
    from pathlib import Path as _Path

    empty: Dict[str, Any] = {"csat_score": None, "csat_positive": 0, "csat_negative": 0, "total_feedback": 0}
    demo_db = _Path("src/aamad/data/demo_dataset.db")
    if not demo_db.exists():
        return empty
    try:
        engine = create_engine(f"sqlite:///{demo_db}")
        with engine.connect() as conn:
            rows = conn.execute(
                _text(
                    "SELECT feedback FROM support_tickets "
                    "WHERE feedback IS NOT NULL "
                    "AND CAST(feedback AS TEXT) != 'null' "
                    "AND CAST(feedback AS TEXT) != '\"\"'"
                )
            ).fetchall()
    except Exception as e:
        logger.warning("Historical CSAT query error: %s", e)
        return empty

    positive = 0
    negative = 0

    for row in rows:
        try:
            fb = row[0]
            if isinstance(fb, dict):
                if fb.get("helpful") is True or fb.get("value") == "positive":
                    positive += 1
                elif fb.get("helpful") is False or fb.get("value") == "negative":
                    negative += 1
            elif isinstance(fb, str):
                try:
                    parsed = _json.loads(fb)
                    if isinstance(parsed, dict):
                        if parsed.get("helpful") is True or parsed.get("value") == "positive":
                            positive += 1
                        elif parsed.get("helpful") is False or parsed.get("value") == "negative":
                            negative += 1
                    elif isinstance(parsed, bool):
                        if parsed:
                            positive += 1
                        else:
                            negative += 1
                    elif isinstance(parsed, str):
                        if parsed in ["positive", "helpful", "true", "1"]:
                            positive += 1
                        elif parsed in ["negative", "not_helpful", "false", "0"]:
                            negative += 1
                except Exception:
                    if fb in ("positive", "helpful", "1", "true"):
                        positive += 1
                    elif fb in ("negative", "not_helpful", "0", "false"):
                        negative += 1
        except Exception as e:
            logger.warning("CSAT parse error (historical): %s", e)
            continue

    total_feedback = positive + negative
    csat = round(positive / total_feedback * 100, 1) if total_feedback > 0 else None
    return {
        "csat_score": csat,
        "csat_positive": positive,
        "csat_negative": negative,
        "total_feedback": total_feedback,
    }


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.api_route("/health", methods=["GET", "HEAD"])
@limiter.limit("60/minute")
async def health(request: Request) -> dict[str, str]:
    return {"status": "ok", "service": "aamad backend", "timestamp": datetime.now().isoformat()}


@router.post("/api/support", response_model=SupportResponse)
@limiter.limit("10/minute")
async def create_support_ticket(
    request: Request, ticket: SupportTicket
) -> SupportResponse:
    inquiry = ticket.inquiry.strip()
    if not inquiry:
        raise HTTPException(status_code=400, detail="Inquiry text cannot be empty.")

    run_id = str(uuid.uuid4())
    start_time = time.time()

    # Process the support request through the CrewAI flow
    support_flow = SupportFlow()
    await support_flow.kickoff_async({"inquiry": inquiry, "run_id": run_id})
    # Unwrap the StateProxy so Pydantic/pydantic-core sees real Python lists,
    # not LockedListProxy (whose C-level list buffer is always empty).
    final_state = support_flow.state._unwrap()

    wall_time = round(time.time() - start_time, 3)
    execution_time_ms = int(wall_time * 1000)

    # Generate reference ID
    reference_id = (
        final_state.reference_id
        if final_state.escalation_required
        else f"REF-{int(time.time())}"
    )

    # Determine status based on routing action and escalation
    if final_state.routing_action == "awaiting":
        status = "awaiting_customer_info"
    elif final_state.escalation_required:
        status = "pending_human_review"
    else:
        status = "completed"

    # Capture RunMetrics and store in shared metrics_store
    metrics = RunMetrics(
        run_id=run_id,
        reference_id=reference_id,
        status=status,
        started_at=start_time,
        finished_at=time.time(),
        wall_time_sec=wall_time,
        step_count=len(final_state.steps),
        tool_latency_ms={
            step["agent"]: step.get("elapsed_ms", 0)
            for step in final_state.steps
        },
        token_usage={},
        success_rate=1.0 if not final_state.escalation_required else 0.8,
    )
    _svc.metrics_store[reference_id] = metrics

    # Create ticket data for persistence
    ticket_data = SupportTicketData(
        reference_id=reference_id,
        inquiry=inquiry,
        category=final_state.category,
        category_confidence=final_state.category_confidence,
        sentiment=final_state.sentiment,
        sentiment_confidence=final_state.sentiment_confidence,
        urgency=final_state.urgency,
        articles=final_state.articles,
        response=final_state.response,
        response_confidence=final_state.response_confidence,
        escalation_required=final_state.escalation_required,
        escalation_reason=final_state.escalation_reason,
        triggered_keyword=final_state.triggered_keyword,
        steps=final_state.steps,
        knowledge_source=final_state.knowledge_source,
        memory_saved=final_state.memory_saved,
        execution_mode=final_state.execution_mode,
        prompt_template_used=final_state.prompt_template_used,
        skills_used=final_state.skills_used,
        tools_used=final_state.tools_used,
        cache_used=final_state.cache_used,
        status=status,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        run_id=run_id,
        execution_time_ms=execution_time_ms,
        wall_time_sec=wall_time,
        token_usage=final_state.token_usage,
        cost_usd=final_state.cost_usd,
        api_tags=final_state.api_tags,
        quality_evaluation=final_state.quality_evaluation or {},
        pending_action=final_state.pending_action or {},
    )

    # Save to data store
    data_store.save_ticket(ticket_data)

    # Write per-ticket observability summary to SQLite
    _svc.observability_service.finalize_ticket(
        reference_id=reference_id,
        wall_time_sec=wall_time,
        quality_evaluation=final_state.quality_evaluation or {},
    )

    # Handle integrations if enabled
    if ENABLE_MOCK_INTEGRATIONS:
        try:
            if final_state.escalation_required:
                _svc.ticketing_client.create_ticket({
                    "inquiry": inquiry,
                    "category": final_state.category,
                    "urgency": final_state.urgency,
                    "reference_id": reference_id,
                })
                _svc.notification_client.send_support_notification(
                    "support@company.com",
                    ticket_data.model_dump(),
                )
            _svc.notification_client.send_customer_notification(
                "customer@example.com",
                ticket_data.model_dump(),
            )
        except Exception as e:
            logger.error("Integration error: %s", e)

    return SupportResponse(
        inquiry=inquiry,
        category=final_state.category,
        category_confidence=final_state.category_confidence,
        sentiment=final_state.sentiment,
        sentiment_confidence=final_state.sentiment_confidence,
        urgency=final_state.urgency,
        articles=final_state.articles,
        response=final_state.response,
        response_confidence=final_state.response_confidence,
        escalation_required=final_state.escalation_required,
        escalation_reason=final_state.escalation_reason,
        reference_id=reference_id,
        triggered_keyword=final_state.triggered_keyword,
        steps=final_state.steps,
        knowledge_source=final_state.knowledge_source,
        memory_saved=final_state.memory_saved,
        execution_mode=final_state.execution_mode,
        prompt_template_used=final_state.prompt_template_used,
        tools_used=final_state.tools_used,
        skills_used=final_state.skills_used,
        cache_used=final_state.cache_used,
        run_id=run_id,
        wall_time_sec=wall_time,
        token_usage=final_state.token_usage or None,
        cost_usd=final_state.cost_usd or None,
        routing_action=final_state.routing_action or None,
        routing_reason=final_state.routing_reason or None,
        routing_missing_info=final_state.routing_missing_info or None,
        api_tags=final_state.api_tags or None,
        quality_evaluation=final_state.quality_evaluation or None,
        pending_action=final_state.pending_action or None,
    )


@router.get("/api/support/{reference_id}/status", response_model=StatusResponse)
async def get_ticket_status(reference_id: str) -> StatusResponse:
    """Get the status of a support ticket."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return StatusResponse(
        reference_id=ticket.reference_id,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        escalation_required=ticket.escalation_required,
        escalation_reason=ticket.escalation_reason,
    )


@router.get("/api/support/{reference_id}/steps", response_model=StepsResponse)
async def get_ticket_steps(reference_id: str) -> StepsResponse:
    """Get the execution steps of a support ticket."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return StepsResponse(
        reference_id=ticket.reference_id,
        steps=ticket.steps,
        status=ticket.status,
    )


@router.get("/api/support/{reference_id}/trace", response_model=TraceResponse)
async def get_ticket_trace(
    reference_id: str, _=Depends(verify_api_key)
) -> TraceResponse:
    """Get observability trace for a support ticket execution."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TraceResponse(
        reference_id=ticket.reference_id,
        run_id=ticket.run_id or "",
        steps=ticket.steps,
        total_steps=len(ticket.steps),
        execution_time_ms=ticket.execution_time_ms,
        tools_used=ticket.tools_used,
        tracing_enabled=True,
    )


@router.get("/api/metrics/summary")
async def get_metrics_summary(_=Depends(verify_api_key)) -> Dict[str, Any]:
    """Aggregate performance metrics across all tickets in current dataset mode."""
    tickets = (
        _get_demo_tickets()
        if _svc.dataset_mode == "historical"
        else data_store.get_all_tickets()
    )
    if not tickets:
        return {
            "total_runs": 0,
            "avg_wall_time_sec": 0.0,
            "success_rate": 1.0,
            "total_escalated": 0,
            "avg_step_count": 0.0,
            "slowest_tool": None,
            "fastest_run_sec": 0.0,
            "slowest_run_sec": 0.0,
            "csat_score": None,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "total_feedback": 0,
            "feedback_rate": 0,
        }

    total = len(tickets)
    total_escalated = sum(1 for t in tickets if t.escalation_required)
    avg_wall_time = sum(t.execution_time_ms for t in tickets) / total / 1000
    success_rate = round((total - total_escalated) / total, 3)
    avg_step_count = round(sum(len(t.steps) for t in tickets) / total, 1)

    tool_times: Dict[str, list] = {}
    for ticket in tickets:
        for step in ticket.steps:
            details = step.get("details", {})
            tool = details.get("tool_used")
            exec_time = details.get("execution_time")
            if tool and exec_time:
                tool_times.setdefault(tool, []).append(float(exec_time))

    slowest_tool = None
    if tool_times:
        slowest_tool = max(
            tool_times, key=lambda t: sum(tool_times[t]) / len(tool_times[t])
        )

    run_times = [t.execution_time_ms / 1000 for t in tickets if t.execution_time_ms]
    fastest = round(min(run_times), 3) if run_times else 0.0
    slowest = round(max(run_times), 3) if run_times else 0.0

    if _svc.dataset_mode == "historical":
        csat_metrics = _get_historical_csat_metrics()
    else:
        csat_metrics = data_store.get_csat_metrics()

    csat_score = csat_metrics["csat_score"]
    helpful_count = csat_metrics["csat_positive"]
    not_helpful_count = csat_metrics["csat_negative"]
    total_feedback = csat_metrics["total_feedback"]

    obs_summary = _svc.observability_service.get_summary()

    return {
        "total_runs": total,
        "avg_wall_time_sec": round(avg_wall_time, 3),
        "success_rate": success_rate,
        "total_escalated": total_escalated,
        "avg_step_count": avg_step_count,
        "slowest_tool": slowest_tool,
        "fastest_run_sec": fastest,
        "slowest_run_sec": slowest,
        "csat_score": csat_score,
        "csat_positive": helpful_count,
        "csat_negative": not_helpful_count,
        "total_feedback": total_feedback,
        "feedback_rate": round((total_feedback / total) * 100) if total > 0 else 0,
        "agent_performance": obs_summary.get("agent_performance", {}),
        "tool_usage": obs_summary.get("tool_usage", {}),
        "total_llm_calls": obs_summary.get("llm_calls", 0),
        "total_events": obs_summary.get("total_events", 0),
        "avg_tool_latency_ms": obs_summary.get("avg_latency_ms", 0),
        "total_real_cost_usd": obs_summary.get("total_cost_usd", 0.0),
    }


@router.get("/api/support/{reference_id}/metrics", response_model=RunMetrics)
async def get_ticket_metrics(
    reference_id: str, _=Depends(verify_api_key)
) -> RunMetrics:
    """Return RunMetrics for a specific ticket (in-memory, current session only)."""
    if reference_id not in _svc.metrics_store:
        raise HTTPException(
            status_code=404, detail="Metrics not found for this ticket"
        )
    return _svc.metrics_store[reference_id]


@router.get("/api/observability/summary")
async def get_observability_summary(_=Depends(verify_api_key)) -> dict:
    """Get aggregate observability metrics (SQLite-backed)."""
    return _svc.observability_service.get_summary()


@router.get("/api/observability/tickets/{reference_id}")
async def get_ticket_observability(
    reference_id: str,
    _=Depends(verify_api_key),
) -> dict:
    """Get structured observability events for a ticket (SQLite-backed)."""
    events = _svc.observability_service.get_events(reference_id)
    if not events:
        raise HTTPException(
            status_code=404,
            detail="No observability events found for this ticket",
        )
    total_tokens = sum(
        e.get("total_tokens") or e.get("estimated_tokens", 0) for e in events
    )
    llm_calls = sum(
        1 for e in events
        if e.get("execution_mode") == "llm" or e.get("llm_used", False)
    )
    return {
        "reference_id": reference_id,
        "events": events,
        "total_events": len(events),
        "total_latency_ms": sum(e.get("latency_ms", 0) for e in events),
        "llm_calls": llm_calls,
        "total_tokens": total_tokens,
    }


@router.post("/api/support/{reference_id}/feedback")
async def submit_feedback(reference_id: str, feedback: FeedbackRequest):
    """Submit feedback for a support ticket."""
    logger.info(
        "Feedback received: ref=%s helpful=%s reason=%s",
        reference_id, feedback.helpful, feedback.feedback_reason,
    )

    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    result = data_store.save_feedback(
        reference_id=reference_id,
        helpful=feedback.helpful,
        feedback_reason=feedback.feedback_reason or feedback.comments,
    )
    logger.info("Feedback saved: ref=%s result=%s", reference_id, result)
    return {"success": True, "message": "Feedback submitted successfully", "reference_id": reference_id}


@router.post("/api/support/{reference_id}/approve")
async def approve_ticket(reference_id: str, _=Depends(verify_api_key)):
    """Approve a support ticket (mark as resolved)."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "pending_human_review":
        raise HTTPException(
            status_code=400, detail="Ticket is not pending human review"
        )

    data_store.update_ticket_status(reference_id, "approved")

    if ENABLE_MOCK_INTEGRATIONS:
        try:
            _svc.ticketing_client.update_ticket_status(
                f"EXT-{reference_id}", "resolved"
            )
        except Exception as e:
            logger.error("Integration error: %s", e)

    return {"message": "Ticket approved successfully", "reference_id": reference_id}


@router.post("/api/support/{reference_id}/reject")
async def reject_ticket(reference_id: str, _=Depends(verify_api_key)):
    """Reject a support ticket (requires revision)."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "pending_human_review":
        raise HTTPException(
            status_code=400, detail="Ticket is not pending human review"
        )

    data_store.update_ticket_status(reference_id, "rejected")

    if ENABLE_MOCK_INTEGRATIONS:
        try:
            _svc.ticketing_client.update_ticket_status(
                f"EXT-{reference_id}", "needs_revision"
            )
        except Exception as e:
            logger.error("Integration error: %s", e)

    return {"message": "Ticket rejected and marked for revision", "reference_id": reference_id}


@router.post("/api/support/{reference_id}/await-customer")
async def await_customer_info(reference_id: str, _=Depends(verify_api_key)):
    """Mark ticket as awaiting customer information."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status not in ("pending_human_review", "awaiting_customer_info"):
        raise HTTPException(
            status_code=400,
            detail="Ticket cannot be set to awaiting from current status",
        )

    data_store.update_ticket_status(reference_id, "awaiting_customer_info")
    return {"message": "Ticket awaiting customer response", "reference_id": reference_id}


@router.get("/api/tickets")
async def get_all_tickets_endpoint(_=Depends(verify_api_key)):
    """Get all tickets from the current dataset mode."""
    if _svc.dataset_mode == "historical":
        tickets = _get_demo_tickets()
    else:
        tickets = data_store.get_all_tickets()
        tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)
    return [ticket.model_dump() for ticket in tickets]


@router.get("/api/dataset/mode")
async def get_dataset_mode():
    """Get current dataset mode and ticket counts for both modes."""
    from pathlib import Path as _Path
    return {
        "mode": _svc.dataset_mode,
        "live_tickets": _get_ticket_count("live"),
        "historical_tickets": _get_ticket_count("historical"),
        "demo_dataset_exists": _Path("src/aamad/data/demo_dataset.db").exists(),
    }


@router.post("/api/dataset/mode")
async def set_dataset_mode(payload: dict, _=Depends(verify_api_key)):
    """Switch dataset mode. Historical mode reads demo_dataset.db (read-only)."""
    from pathlib import Path as _Path

    mode = payload.get("mode", "live")
    if mode not in ("live", "historical"):
        raise HTTPException(
            status_code=400, detail="Mode must be 'live' or 'historical'"
        )

    if mode == "historical" and not _Path("src/aamad/data/demo_dataset.db").exists():
        raise HTTPException(
            status_code=404,
            detail="Demo dataset not found. Create demo_dataset.db first.",
        )

    _svc.dataset_mode = mode
    return {
        "success": True,
        "mode": _svc.dataset_mode,
        "live_tickets": _get_ticket_count("live"),
        "historical_tickets": _get_ticket_count("historical"),
        "message": f"Switched to {mode} mode",
    }


@router.delete("/api/tickets/clear")
async def clear_tickets(_=Depends(verify_api_key)):
    """Delete all tickets and create an automatic backup first."""
    import shutil
    from pathlib import Path

    db_path = Path("src/aamad/data/tickets.db")
    backup_path = None
    if db_path.exists():
        backup_name = f"support_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        backup_path = Path(f"src/aamad/data/{backup_name}")
        shutil.copy2(db_path, backup_path)

    with data_store.SessionLocal() as session:
        result = session.execute(sa_text("DELETE FROM support_tickets"))
        session.commit()
        deleted = result.rowcount

    return {
        "success": True,
        "deleted_tickets": deleted,
        "backup_created": str(backup_path) if backup_path else None,
        "backup_filename": backup_path.name if backup_path else None,
        "message": (
            f"Cleared {deleted} tickets. "
            f"Backup: {backup_path.name if backup_path else 'none'}"
        ),
    }


@router.get("/api/tickets/backups")
async def list_backups(_=Depends(verify_api_key)):
    """List all automatic database backups."""
    from pathlib import Path
    data_dir = Path("src/aamad/data")
    backups = sorted(data_dir.glob("support_backup_*.db"), reverse=True)
    return {
        "backups": [
            {
                "filename": b.name,
                "created_at": b.stem.replace("support_backup_", ""),
                "size_kb": round(b.stat().st_size / 1024, 1),
            }
            for b in backups
        ]
    }


@router.post("/api/tickets/restore")
async def restore_backup(payload: dict, _=Depends(verify_api_key)):
    """Restore the database from a named backup file."""
    import shutil
    from pathlib import Path

    backup_file = payload.get("backup_file")
    if not backup_file:
        raise HTTPException(status_code=400, detail="backup_file is required")
    backup_path = Path(f"src/aamad/data/{backup_file}")
    db_path = Path("src/aamad/data/tickets.db")
    if not backup_path.exists():
        raise HTTPException(
            status_code=404, detail=f"Backup {backup_file} not found"
        )
    shutil.copy2(backup_path, db_path)
    return {
        "success": True,
        "restored_from": backup_file,
        "message": "Database restored successfully",
    }
