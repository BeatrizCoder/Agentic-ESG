"""CS Task factories — compact schemas embedded inline, strict JSON-only output."""

import json
from crewai import Task

from .definitions import (
    climate_analyst_agent, esg_strategist_agent,
    report_writer_agent, quality_judge_agent,
)


_ESG_SCHEMA = """{
  "csrd_exposure": "low|medium|high|critical",
  "csrd_articles": ["<string>", ...],
  "csrd_summary": "<one sentence>",
  "issb_s2_exposure": "low|medium|high|critical",
  "issb_s2_scenarios": ["<string>", ...],
  "issb_s2_summary": "<one sentence>",
  "eu_taxonomy_alignment": "aligned|partial|misaligned|not_assessed",
  "eu_taxonomy_criteria": ["<string>", ...],
  "eu_taxonomy_summary": "<one sentence>",
  "lgpd_note": "No personal data processed in this analysis",
  "compliance_urgency": "low|medium|high|critical",
  "priority_framework": "CSRD|ISSB_S2|EU_TAXONOMY",
  "key_compliance_findings": ["<string>", "<string>", "<string>"],
  "double_materiality": {
    "physical_risk_summary": "<what climate does to this operation — 1-2 sentences using REAL trend numbers>",
    "physical_impacts": ["<specific production/infra/supply-chain impact>", "<impact 2>", "<impact 3>"],
    "impact_risk_summary": "<what this sector's operations do to the local climate — 1-2 sentences>",
    "impact_risks": ["<water consumption>", "<groundwater pressure>", "<natural resource competition with communities>"]
  }
}"""

_REPORT_SCHEMA = """{
  "risk_score": <int 0-100>,
  "risk_level": "low|medium|high|critical",
  "risk_badge_label": "LOW RISK|MEDIUM RISK|HIGH RISK|CRITICAL RISK",
  "executive_summary": "<Start with region name, e.g. 'Brasília, Brazil scores 72/100…'. 3-4 sentences total.>",
  "key_metrics": {
    "temp_change_label": "<e.g. +1.2°C vs baseline>",
    "precip_change_label": "<e.g. -18% vs baseline>",
    "compliance_exposure_label": "<e.g. CSRD · ISSB S2>",
    "hottest_year": <int>,
    "driest_year": <int>
  },
  "recommendations": [
    {
      "rank": <int>,
      "framework": "CSRD|ISSB_S2|EU_TAXONOMY|OPERATIONAL",
      "article": "<string>",
      "action": "<verb-led sentence>",
      "timeline": "immediate|short_term|medium_term",
      "priority": "critical|high|medium"
    }
  ],
  "offset_targets": [
    {
      "category": "Reforestation",
      "requirement": "<MUST include real numbers from the analysis e.g. '-23.58%/decade precipitation decline' or '+0.765°C/decade warming'>",
      "urgency": "immediate|short_term|long_term",
      "framework_ref": "CSRD ESRS E4-6"
    },
    {
      "category": "Water Security",
      "requirement": "<MUST cite real precipitation_total_mm or precip_trend from the data>",
      "urgency": "immediate|short_term|long_term",
      "framework_ref": "ISSB S2 paragraph 10b"
    },
    {
      "category": "Soil & Biodiversity",
      "requirement": "<text specific to the detected regional biome using real solar/temp data>",
      "urgency": "immediate|short_term|long_term",
      "framework_ref": "EU Taxonomy CCA Annex II"
    }
  ]
}"""


def make_climate_analysis_task(climate_task_input_str: str) -> Task:
    try:
        inp = json.loads(climate_task_input_str)
        metrics = inp.get("metrics", {})
        sample_years = inp.get("sample_years", [])
        region = inp.get("region", "")
        sector = inp.get("sector", "General")
    except Exception:
        metrics = {}
        sample_years = []
        region = ""
        sector = "General"

    metrics_json = json.dumps(metrics, indent=2)
    sample_json = json.dumps(sample_years, indent=2)

    return Task(
        description=f"""You are a Climate Interpreter for {region!r} ({sector} sector).

Pre-calculated climate risk metrics from the Python engine:
{metrics_json}

Recent climate data — last 5 years:
{sample_json}

Write 2-3 executive sentences explaining what these numbers mean in plain language.
Highlight compound risks (e.g. heat + drought together).
Provide context for an ESG Strategist who will use this to map compliance obligations.

Maximum 150 words. No bullet points. No headers. Just 2-3 clear executive sentences.""",
        expected_output="2-3 sentences of executive climate interpretation, maximum 150 words, no JSON, no bullet points",
        agent=climate_analyst_agent,
    )


def make_esg_strategy_task(climate_summary: str, region_label: str, sector: str = "General") -> Task:
    return Task(
        description=f"""Map these climate risk findings for {region_label!r} to ESG compliance obligations.
Return ONLY the JSON object below. No prose, no markdown, no extra keys.

SECTOR: {sector}
CLIMATE FINDINGS:
{climate_summary}

MAPPING RULES:
- heat_stress_risk/drought_risk → ESRS E1 (climate change) and ESRS E3 (water)
- flood_risk → ESRS E1 and EU Taxonomy climate change adaptation
- ISSB S2 chronic = temperature/precipitation trends; acute = anomaly years
- compliance_urgency must be at least "high" if drought_risk or heat_stress_risk is high/critical

DOUBLE MATERIALITY RULES (use the real numbers from CLIMATE FINDINGS above):
- physical_risk_summary: "For {sector} operations in {region_label}, the [REAL temp_trend]°C/decade warming and [REAL precip_trend]%/decade precipitation change indicate [specific operational risk]"
- physical_impacts: list 3 operational impacts specific to {sector} (production, infrastructure, supply chain)
- impact_risk_summary: describe how {sector} operations affect the local climate (water consumption, land use, emissions)
- impact_risks: list 3 inside-out impacts (water consumption patterns, groundwater pressure, community resource competition)

RETURN EXACTLY THIS JSON STRUCTURE (replace <placeholders>):
{_ESG_SCHEMA}""",
        expected_output="Valid JSON matching the ESG schema, including double_materiality object",
        agent=esg_strategist_agent,
    )


def make_report_task(
    climate_summary: str,
    compliance_summary: str,
    region_label: str,
    latitude: float,
    longitude: float,
) -> Task:
    return Task(
        description=f"""Generate an executive climate risk report for {region_label!r} ({latitude:.4f}, {longitude:.4f}).
Return ONLY the JSON object below. No prose, no markdown, no extra keys.

RISK SCORE MATRIX (sum points, cap at 100):
heat_stress_risk=high→+20, =critical→+35
drought_risk=high→+15, =critical→+25
flood_risk=high→+15, =critical→+25
csrd_exposure=high→+10, =critical→+20
issb_s2_exposure=high→+8, =critical→+15
eu_taxonomy_alignment=misaligned→+5
compliance_urgency=critical→+10
temp_trend_c_per_decade>0.5→+5
precip_trend_pct_per_decade<-10→+5

CLIMATE FINDINGS:
{climate_summary}

COMPLIANCE MAPPING:
{compliance_summary}

Provide 4-6 recommendations ranked by priority.
executive_summary must start with the region name. Example: '{region_label} scores X/100…'. Then mention the risk_score number and lead with the main risk driver.

OFFSET TARGETS RULES — each requirement MUST quote real numbers from CLIMATE FINDINGS:
- Use exact values like temp_trend_c_per_decade, precip_trend_pct_per_decade, baseline_precip_mm, latest_precip_mm
- Example good requirement: "Reforest minimum 15% of watershed area given -23.6%/decade precipitation decline and +0.77°C/decade warming"
- Example bad requirement: "Reforestation needed due to climate change" ← generic, unacceptable

RETURN EXACTLY THIS JSON STRUCTURE (replace <placeholders>):
{_REPORT_SCHEMA}""",
        expected_output="Valid JSON with risk_score, risk_level, executive_summary, recommendations, key_metrics, offset_targets",
        agent=report_writer_agent,
    )


_JUDGE_SCHEMA = """{
  "confidence_score": <int 0-100>,
  "data_coherence_score": <int 0-100>,
  "data_coherence_finding": "<one sentence>",
  "regulatory_precision_score": <int 0-100>,
  "regulatory_precision_finding": "<one sentence>",
  "risk_score_consistency_score": <int 0-100>,
  "risk_score_consistency_finding": "<one sentence>",
  "issues": ["<string>", ...],
  "strengths": ["<string>", ...],
  "verdict": "validated|needs_review|flagged"
}"""

_SCORING_MATRIX = """heat_stress_risk=high→+20, =critical→+35
drought_risk=high→+15, =critical→+25
flood_risk=high→+15, =critical→+25
csrd_exposure=high→+10, =critical→+20
issb_s2_exposure=high→+8, =critical→+15
eu_taxonomy_alignment=misaligned→+5
compliance_urgency=critical→+10
temp_trend_c_per_decade>0.5→+5
precip_trend_pct_per_decade<-10→+5
(sum, cap at 100)"""


def make_quality_judge_task(
    climate_summary: str,
    compliance_summary: str,
    report_summary: str,
) -> Task:
    return Task(
        description=f"""IMPORTANT: Your ENTIRE response must be a single JSON object starting with {{ and ending with }}.
No preamble, no explanation, no markdown. Just the JSON.

You are an independent auditor. Evaluate this ESG climate risk report
on exactly three dimensions.

SCORING MATRIX (used by the Report Writer):
{_SCORING_MATRIX}

CLIMATE FINDINGS (from Agent 2):
{climate_summary}

COMPLIANCE MAPPING (from Agent 3):
{compliance_summary}

REPORT OUTPUT (from Agent 4):
{report_summary}

EVALUATION RULES:
1. DATA COHERENCE (0-100): Do the risk levels and conclusions follow logically from the
   raw numbers? E.g. if temp_trend=0.3°C/decade, heat_stress_risk=critical would be
   incoherent. Deduct 10 pts per conclusion that contradicts the input data.

2. REGULATORY PRECISION (0-100): Are the cited CSRD/ISSB S2/EU Taxonomy articles real
   and correctly applied? ESRS E1 = climate change, ESRS E3 = water, ISSB S2 = physical
   and transition climate risks, EU Taxonomy DNSH = Do No Significant Harm criteria.
   Deduct 15 pts per article that is invented or misapplied.

3. RISK SCORE CONSISTENCY (0-100): Manually apply the scoring matrix to the reported
   risk levels and check whether the numeric risk_score is within ±10 of the expected
   value. Deduct 20 pts if the gap exceeds 10, 10 pts if gap is 5-10.

confidence_score = round(data_coherence*0.40 + regulatory_precision*0.35 + risk_score_consistency*0.25)

RETURN EXACTLY THIS JSON (replace <placeholders>):
{_JUDGE_SCHEMA}""",
        expected_output="Valid JSON with confidence_score, three dimension scores, issues, strengths, and verdict",
        agent=quality_judge_agent,
    )
