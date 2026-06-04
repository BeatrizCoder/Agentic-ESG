"""CS Pydantic request / response models."""

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator, model_validator


class AnalyzeRequest(BaseModel):
    latitude: float = Field(
        ...,
        ge=-90,
        le=90,
        description="Latitude in decimal degrees (-90 to 90)",
    )
    longitude: float = Field(
        ...,
        ge=-180,
        le=180,
        description="Longitude in decimal degrees (-180 to 180)",
    )
    region_label: str = Field(
        "",
        max_length=120,
        description="Human-readable location name",
    )
    start_year: int = Field(
        2014,
        ge=2000,
        le=2025,
        description="Start year for historical data (2000-2025)",
    )
    end_year: int = Field(
        2023,
        ge=2001,
        le=2050,
        description="End year for analysis (2001-2050)",
    )
    sector: str = Field(
        "General",
        max_length=60,
        description="Industry sector for tailored analysis",
    )
    scenario: str = Field(
        "SSP2-4.5",
        pattern="^(SSP1-2\\.6|SSP2-4\\.5|SSP5-8\\.5)$",
        description="IPCC emissions scenario",
    )

    @field_validator("region_label")
    @classmethod
    def validate_region_label(cls, v: str) -> str:
        """Ensure region label is not just whitespace."""
        if v and not v.strip():
            raise ValueError("region_label cannot be only whitespace")
        return v.strip() if v else ""

    @field_validator("latitude", "longitude")
    @classmethod
    def validate_coordinates(cls, v: float, info) -> float:
        """Validate coordinate precision (Field constraints are the primary guard)."""
        return round(v, 6)  # Limit to 6 decimal places (~0.1m precision)

    @model_validator(mode="after")
    def validate_year_range(self) -> "AnalyzeRequest":
        """Ensure end_year is after start_year."""
        if self.end_year <= self.start_year:
            raise ValueError(
                f"end_year ({self.end_year}) must be greater than "
                f"start_year ({self.start_year})"
            )
        
        # Warn if range is too large (performance consideration)
        year_span = self.end_year - self.start_year
        if year_span > 50:
            raise ValueError(
                f"Year range too large ({year_span} years). "
                "Maximum allowed is 50 years."
            )
        
        return self


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
    hitl_required: bool = False
    hitl_reasons: list[str] = []
    transparency: dict[str, Any] = {}


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


class BatchRowResult(BaseModel):
    region: str = ""
    latitude: float = 0.0
    longitude: float = 0.0
    sector: str = "General"
    scenario: str = "SSP2-4.5"
    risk_score: int = 0
    risk_level: str = ""
    investment_status: str = ""
    confidence_score: int = 0
    analysis_id: str = ""
    error: str = ""
    status: str = "completed"  # "completed" | "error"


class BatchAnalysisResponse(BaseModel):
    total: int
    completed: int
    failed: int
    results: list[BatchRowResult]
