"""Pytest configuration and shared fixtures."""

import pytest
from httpx import AsyncClient


@pytest.fixture
def mock_nasa_response():
    """Mock NASA POWER API response."""
    return {
        "properties": {
            "parameter": {
                "T2M": {
                    "20200101": 25.5,
                    "20200102": 26.0,
                    "20200103": 24.8,
                },
                "PRECTOTCORR": {
                    "20200101": 2.5,
                    "20200102": 0.0,
                    "20200103": 1.2,
                },
                "ALLSKY_SFC_SW_DWN": {
                    "20200101": 5.8,
                    "20200102": 6.2,
                    "20200103": 5.5,
                },
            }
        }
    }


@pytest.fixture
def mock_openmeteo_response():
    """Mock OpenMeteo IPCC API response."""
    return {
        "latitude": -23.5505,
        "longitude": -46.6333,
        "daily": {
            "time": ["2026-01-01", "2026-01-02", "2026-01-03"],
            "temperature_2m_mean": [26.5, 27.0, 25.8],
            "precipitation_sum": [3.5, 0.0, 2.2],
        }
    }


@pytest.fixture
def sample_analysis_request():
    """Sample analysis request payload."""
    return {
        "latitude": -23.5505,
        "longitude": -46.6333,
        "region_label": "São Paulo, Brazil",
        "start_year": 2020,
        "end_year": 2023,
        "sector": "General",
        "scenario": "SSP2-4.5",
    }


@pytest.fixture
async def async_client():
    """Async HTTP client for testing."""
    async with AsyncClient() as client:
        yield client

# Made with Bob
