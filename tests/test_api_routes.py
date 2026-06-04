"""Tests for FastAPI routes."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch
from src.aesg.backend import app


client = TestClient(app)


def test_health_endpoint():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "agentic-esg"
    assert "timestamp" in data


def test_health_endpoint_head():
    """Test health check HEAD request."""
    response = client.head("/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_analyze_endpoint_validation_error():
    """Test analyze endpoint with invalid input."""
    # Invalid: end_year <= start_year
    response = client.post(
        "/api/analyze",
        json={
            "latitude": -23.5505,
            "longitude": -46.6333,
            "region_label": "São Paulo",
            "start_year": 2023,
            "end_year": 2020,  # Invalid: before start_year
            "sector": "General",
            "scenario": "SSP2-4.5",
        }
    )
    assert response.status_code == 400
    assert "end_year must be greater than start_year" in response.json()["detail"]


@pytest.mark.asyncio
async def test_analyze_endpoint_success(sample_analysis_request):
    """Test successful analysis request."""
    with patch("src.cs.api.routes.run_analysis") as mock_run_analysis:
        # Mock the analysis result
        mock_result = AsyncMock()
        mock_result.analysis_id = "CS-1234567890"
        mock_result.region_label = "São Paulo, Brazil"
        mock_result.latitude = -23.5505
        mock_result.longitude = -46.6333
        mock_result.risk_score = 65
        mock_result.risk_level = "High"
        mock_result.risk_badge_label = "Conditioned"
        mock_result.executive_summary = "Test summary"
        mock_result.recommendations = []
        mock_result.key_metrics = {}
        mock_result.climate_findings = {}
        mock_result.compliance_mapping = {}
        mock_result.annual_records = []
        mock_result.pipeline_metadata = {}
        mock_result.confidence_score = 85
        mock_result.quality_evaluation = {}
        mock_result.openmeteo_data = {}
        mock_result.offset_targets = []
        mock_result.sector = "General"
        mock_result.pipeline_duration_sec = 25.5
        mock_result.created_at = "2026-06-02T00:00:00Z"
        mock_result.error = ""
        
        mock_run_analysis.return_value = mock_result
        
        response = client.post("/api/analyze", json=sample_analysis_request)
        
        assert response.status_code == 200
        data = response.json()
        assert data["analysis_id"] == "CS-1234567890"
        assert data["risk_score"] == 65
        assert data["risk_level"] == "High"


def test_get_analyses_list():
    """Test listing recent analyses."""
    with patch("src.cs.api.routes.get_recent_analyses") as mock_get_recent:
        mock_get_recent.return_value = []
        
        response = client.get("/api/analyses")
        
        assert response.status_code == 200
        assert isinstance(response.json(), list)


def test_get_analysis_not_found():
    """Test getting non-existent analysis."""
    with patch("src.cs.api.routes._db_get") as mock_db_get:
        mock_db_get.return_value = None
        
        response = client.get("/api/analyses/CS-nonexistent")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


def test_delete_analysis_not_found():
    """Test deleting non-existent analysis."""
    with patch("src.cs.api.routes._db_delete") as mock_db_delete:
        mock_db_delete.return_value = False
        
        response = client.delete("/api/analyses/CS-nonexistent")
        
        assert response.status_code == 404


def test_get_history_without_session_id():
    """Test getting history without session ID header."""
    response = client.get("/api/analyses/history")
    
    assert response.status_code == 400
    assert "X-Session-ID" in response.json()["detail"]


def test_cors_headers():
    """Test CORS headers are present."""
    response = client.options("/api/analyze")
    
    assert response.status_code == 204
    assert "access-control-allow-origin" in response.headers
    assert "access-control-allow-methods" in response.headers

# Made with Bob
