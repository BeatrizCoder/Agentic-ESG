"""CS Pydantic request / response models."""

from typing import Any, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    region_label: str = Field("", max_length=120)
    start_year: int = Field(2014, ge=2000, le=2025)
    end_year: int = Field(2023, ge=2001, le=2050)
    sector: str = Field("General", max_length=60)
    scenario: str = Field("SSP2-4.5", pattern="^(SSP1-2\\.6|SSP2-4\\.5|SSP5-8\\.5)$")


class RecommendationItem(BaseModel):
    rank: int
    framework: str
    article: str
    action: str
    timeline: str
    priority: str


class KeyMetrics(BaseModel):
    temp_change_label: str = ""
    precip_change_label: str = ""
    compliance_exposure_label: str = ""
    hottest_year: Optional[int] = None
    driest_year: Optional[int] = None


class AnalysisResponse(BaseModel):
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
    pipeline_metadata: dict[str, Any] = {}
    confidence_score: int = 0
    quality_evaluation: dict[str, Any] = {}
    openmeteo_data: dict[str, Any] = {}
    offset_targets: list[dict[str, Any]] = []
    sector: str = "General"
    pipeline_duration_sec: float
    created_at: str
    error: str = ""


class AnalysisSummary(BaseModel):
    analysis_id: str
    region_label: str
    latitude: float
    longitude: float
    risk_score: int
    risk_level: str
    risk_badge_label: str
    created_at: str
    pipeline_duration_sec: float
