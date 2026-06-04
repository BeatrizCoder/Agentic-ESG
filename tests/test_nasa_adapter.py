"""Tests for NASA POWER API adapter."""

import pytest
from unittest.mock import AsyncMock, patch
from src.aesg.data.nasa_adapter import (
    fetch_climate_data,
    _aggregate_by_year,
    AnnualClimateRecord,
)


@pytest.mark.asyncio
async def test_fetch_climate_data_success(mock_nasa_response):
    """Test successful NASA POWER API fetch."""
    with patch("httpx.AsyncClient") as mock_client:
        mock_response = AsyncMock()
        mock_response.json.return_value = mock_nasa_response
        mock_response.raise_for_status = AsyncMock()
        
        mock_client.return_value.__aenter__.return_value.build_request.return_value.url = (
            "https://power.larc.nasa.gov/api/temporal/daily/point"
        )
        mock_client.return_value.__aenter__.return_value.send.return_value = mock_response
        
        result = await fetch_climate_data(
            latitude=-23.5505,
            longitude=-46.6333,
            region_label="São Paulo",
            start_year=2020,
            end_year=2020,
        )
        
        assert result.latitude == -23.5505
        assert result.longitude == -46.6333
        assert result.region_label == "São Paulo"
        assert len(result.annual_records) == 1
        assert result.annual_records[0].year == 2020
        assert result.source == "NASA POWER API v2.5"


@pytest.mark.asyncio
async def test_fetch_climate_data_invalid_coordinates():
    """Test fetch with invalid coordinates."""
    with pytest.raises(Exception):
        await fetch_climate_data(
            latitude=999.0,  # Invalid latitude
            longitude=-46.6333,
            start_year=2020,
            end_year=2020,
        )


def test_aggregate_by_year():
    """Test annual aggregation of daily data."""
    parameters = {
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
    
    records = _aggregate_by_year(parameters, -23.5505, -46.6333)
    
    assert len(records) == 1
    assert records[0].year == 2020
    assert records[0].latitude == -23.5505
    assert records[0].longitude == -46.6333
    assert records[0].temp_mean_celsius == pytest.approx(25.433, rel=0.01)
    assert records[0].temp_max_celsius == 26.0
    assert records[0].temp_min_celsius == 24.8
    assert records[0].precip_total_mm == pytest.approx(3.7, rel=0.1)
    assert records[0].days_sampled == 3


def test_aggregate_by_year_with_missing_values():
    """Test aggregation handles missing values (-999.0)."""
    parameters = {
        "T2M": {
            "20200101": 25.5,
            "20200102": -999.0,  # Missing value
            "20200103": 24.8,
        },
        "PRECTOTCORR": {
            "20200101": 2.5,
            "20200102": 0.0,
            "20200103": -999.0,  # Missing value
        },
        "ALLSKY_SFC_SW_DWN": {
            "20200101": 5.8,
            "20200102": 6.2,
            "20200103": 5.5,
        },
    }
    
    records = _aggregate_by_year(parameters, -23.5505, -46.6333)
    
    assert len(records) == 1
    # Should only use valid values (not -999.0)
    assert records[0].temp_mean_celsius == pytest.approx(25.15, rel=0.01)
    assert records[0].precip_total_mm == pytest.approx(2.5, rel=0.1)


def test_aggregate_by_year_multiple_years():
    """Test aggregation across multiple years."""
    parameters = {
        "T2M": {
            "20200101": 25.5,
            "20210101": 26.5,
        },
        "PRECTOTCORR": {
            "20200101": 2.5,
            "20210101": 3.5,
        },
        "ALLSKY_SFC_SW_DWN": {
            "20200101": 5.8,
            "20210101": 6.8,
        },
    }
    
    records = _aggregate_by_year(parameters, -23.5505, -46.6333)
    
    assert len(records) == 2
    assert records[0].year == 2020
    assert records[1].year == 2021
    assert records[0].temp_mean_celsius == 25.5
    assert records[1].temp_mean_celsius == 26.5

# Made with Bob
