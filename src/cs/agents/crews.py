"""CS CrewAI crew runner — three sequential single-agent crews."""

import io
import json
import logging
import re
import sys

from crewai import Crew, Process

logger = logging.getLogger(__name__)


def _kickoff_silent(crew: Crew):
    """Run crew.kickoff() suppressing rich/console TTY errors on non-TTY servers."""
    old_stdout, old_stderr = sys.stdout, sys.stderr
    try:
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        return crew.kickoff()
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr


def _get_tokens(result) -> dict:
    """Extract token usage from a CrewOutput object."""
    try:
        usage = result.token_usage
        return {
            "input_tokens":  int(getattr(usage, "prompt_tokens",     0) or getattr(usage, "input_tokens",  0)),
            "output_tokens": int(getattr(usage, "completion_tokens", 0) or getattr(usage, "output_tokens", 0)),
            "total_tokens":  int(getattr(usage, "total_tokens", 0)),
        }
    except Exception:
        return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _extract_json(raw: str) -> dict:
    """Strip markdown fences and parse JSON; falls back to first {...} block."""
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*", cleaned, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
        raise


def run_climate_analysis_crew(serialised_records: str) -> tuple[dict, dict]:
    """Agent 2 — Climate Analyst. Returns (findings, tokens)."""
    from .tasks import make_climate_analysis_task
    from .definitions import climate_analyst_agent

    crew = Crew(
        agents=[climate_analyst_agent],
        tasks=[make_climate_analysis_task(serialised_records)],
        process=Process.sequential,
        verbose=False,
    )
    result = _kickoff_silent(crew)
    tokens = _get_tokens(result)
    try:
        return _extract_json(result.tasks_output[0].raw), tokens
    except Exception as error:
        logger.error("Climate analysis crew parsing failed: %s", error)
        return {"error": str(error), "key_findings": [], "data_quality": "poor"}, tokens


def run_esg_strategy_crew(
    climate_summary: str, region_label: str, sector: str = "General"
) -> tuple[dict, dict]:
    """Agent 3 — ESG Strategist. Returns (compliance_mapping, tokens)."""
    from .tasks import make_esg_strategy_task
    from .definitions import esg_strategist_agent

    crew = Crew(
        agents=[esg_strategist_agent],
        tasks=[make_esg_strategy_task(climate_summary, region_label, sector)],
        process=Process.sequential,
        verbose=False,
    )
    result = _kickoff_silent(crew)
    tokens = _get_tokens(result)
    try:
        return _extract_json(result.tasks_output[0].raw), tokens
    except Exception as error:
        logger.error("ESG strategy crew parsing failed: %s", error)
        return {"error": str(error), "compliance_urgency": "unknown", "key_compliance_findings": []}, tokens


def run_report_crew(
    climate_summary: str,
    compliance_summary: str,
    region_label: str,
    latitude: float,
    longitude: float,
) -> tuple[dict, dict]:
    """Agent 4 — Report Writer. Returns (report, tokens)."""
    from .tasks import make_report_task
    from .definitions import report_writer_agent

    crew = Crew(
        agents=[report_writer_agent],
        tasks=[make_report_task(climate_summary, compliance_summary, region_label, latitude, longitude)],
        process=Process.sequential,
        verbose=False,
    )
    result = _kickoff_silent(crew)
    tokens = _get_tokens(result)
    try:
        return _extract_json(result.tasks_output[0].raw), tokens
    except Exception as error:
        logger.error("Report crew parsing failed: %s", error)
        return {
            "error": str(error), "risk_score": 0, "risk_level": "unknown",
            "executive_summary": "", "recommendations": [],
        }, tokens


def run_quality_judge_crew(
    climate_summary: str,
    compliance_summary: str,
    report_summary: str,
) -> tuple[dict, dict]:
    """Agent 5 — Quality Judge: cross-validates data, regulations, and risk score."""
    from .tasks import make_quality_judge_task
    from .definitions import quality_judge_agent

    crew = Crew(
        agents=[quality_judge_agent],
        tasks=[make_quality_judge_task(climate_summary, compliance_summary, report_summary)],
        process=Process.sequential,
        verbose=False,
    )
    result = _kickoff_silent(crew)
    tokens = _get_tokens(result)
    try:
        return _extract_json(result.tasks_output[0].raw), tokens
    except Exception as error:
        logger.error("Quality judge crew parsing failed: %s", error)
        return {
            "confidence_score": 0, "verdict": "flagged",
            "issues": [str(error)], "strengths": [],
        }, tokens
