"""Sanity tests for known locations using synthetic NASA-like annual records.

These tests run the deterministic climate engine with realistic pre-built
annual records and assert that outputs fall within physically plausible
ranges for each location.  No live API calls are made.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from aesg.pipeline.climate_engine import calculate_climate_risk
from aesg.pipeline.orchestrator import (
    validate_annual_record, global_sanity_check, validate_final_result, IMPOSSIBLE_VALUES,
)


# ── Reference locations ───────────────────────────────────────────────────────

KNOWN_GOOD = [
    {
        "region": "Brasília, Brazil",
        "lat": -15.7801, "lon": -47.9292,
        # Cerrado: hot tropical savanna, pronounced wet/dry season
        "annual_records": [
            {"year": y, "temp_mean_celsius": 21.5 + (y - 2014) * 0.05,
             "precip_total_mm": 1350 - (y - 2014) * 10,
             "solar_mean_kwh_m2": 5.8, "evapotranspiration_mm": 1100, "source": "nasa"}
            for y in range(2014, 2025)
        ],
        "expected": {
            "temp_range":            (20, 28),
            "precip_range":          (600, 1500),
            "risk_range":            (10, 100),
            "trend_temp_positive":   True,
            "trend_precip_negative": True,
        },
    },
    {
        "region": "Amsterdam, Netherlands",
        "lat": 52.3676, "lon": 4.9041,
        # Maritime temperate: mild, wet
        "annual_records": [
            {"year": y, "temp_mean_celsius": 10.5 + (y - 2014) * 0.04,
             "precip_total_mm": 850 + (y - 2014) * 2,
             "solar_mean_kwh_m2": 2.9, "evapotranspiration_mm": 520, "source": "nasa"}
            for y in range(2014, 2025)
        ],
        "expected": {
            "temp_range":  (8, 14),
            "precip_range": (600, 1200),
            "risk_range":  (0, 70),
        },
    },
    {
        "region": "Zurich, Switzerland",
        "lat": 47.3769, "lon": 8.5417,
        # Continental alpine: cool, moderate precip
        "annual_records": [
            {"year": y, "temp_mean_celsius": 9.5 + (y - 2014) * 0.04,
             "precip_total_mm": 1100 + (y - 2014) * 1,
             "solar_mean_kwh_m2": 3.2, "evapotranspiration_mm": 600, "source": "nasa"}
            for y in range(2014, 2025)
        ],
        "expected": {
            "temp_range":  (5, 14),
            "precip_range": (800, 1800),
            "risk_range":  (0, 60),
        },
    },
]


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mean(values):
    return sum(values) / len(values) if values else 0


def run_climate_engine_for(location: dict) -> dict:
    records = location["annual_records"]
    metrics = calculate_climate_risk(records)
    temps   = [r["temp_mean_celsius"] for r in records]
    precips = [r["precip_total_mm"] for r in records]
    return {
        **metrics,
        "temp_mean":   round(_mean(temps), 2),
        "precip_mean": round(_mean(precips), 1),
        # Expose a risk_score proxy for assertion (max of sub-scores)
        "risk_score": int(max(
            metrics.get("drought_score", 0),
            metrics.get("heat_stress_score", 0),
            metrics.get("flood_score", 0),
        )),
    }


# ── Known-location tests ──────────────────────────────────────────────────────

@pytest.mark.parametrize("location", KNOWN_GOOD, ids=[loc["region"] for loc in KNOWN_GOOD])
def test_known_location_temperature(location):
    result = run_climate_engine_for(location)
    exp    = location["expected"]
    temp   = result["temp_mean"]
    lo, hi = exp["temp_range"]
    assert lo <= temp <= hi, (
        f"[{location['region']}] temp_mean={temp}°C outside expected [{lo}, {hi}]"
    )


@pytest.mark.parametrize("location", KNOWN_GOOD, ids=[loc["region"] for loc in KNOWN_GOOD])
def test_known_location_precipitation(location):
    result = run_climate_engine_for(location)
    exp    = location["expected"]
    precip = result["precip_mean"]
    lo, hi = exp["precip_range"]
    assert lo <= precip <= hi, (
        f"[{location['region']}] precip_mean={precip}mm outside expected [{lo}, {hi}]"
    )


@pytest.mark.parametrize("location", KNOWN_GOOD, ids=[loc["region"] for loc in KNOWN_GOOD])
def test_known_location_risk_range(location):
    result = run_climate_engine_for(location)
    exp    = location["expected"]
    risk   = result["risk_score"]
    lo, hi = exp["risk_range"]
    assert lo <= risk <= hi, (
        f"[{location['region']}] risk_score={risk} outside expected [{lo}, {hi}]"
    )


def test_brasilia_warming_trend():
    loc    = next(l for l in KNOWN_GOOD if "Brasília" in l["region"])
    result = run_climate_engine_for(loc)
    assert result.get("temp_trend_c_per_decade", 0) > 0, (
        "Brasília should show a positive warming trend"
    )


def test_brasilia_drying_trend():
    loc    = next(l for l in KNOWN_GOOD if "Brasília" in l["region"])
    result = run_climate_engine_for(loc)
    pt = result.get("precip_trend_pct_per_decade")
    if pt is not None:
        assert pt < 0, "Brasília should show a negative precipitation trend"


# ── validate_annual_record ────────────────────────────────────────────────────

def test_validate_annual_record_good():
    record = {"year": 2020, "temp_mean_celsius": 21.5, "precip_total_mm": 1200, "source": "nasa"}
    assert validate_annual_record(record, "Test") is True


def test_validate_annual_record_bad_temp():
    record = {"year": 2020, "temp_mean_celsius": 55.0, "precip_total_mm": 1200, "source": "nasa"}
    assert validate_annual_record(record, "Test") is False


def test_validate_annual_record_bad_precip():
    record = {"year": 2020, "temp_mean_celsius": 20.0, "precip_total_mm": 9999, "source": "nasa"}
    assert validate_annual_record(record, "Test") is False


def test_validate_annual_record_zero_temp_allowed():
    # 0°C is treated as missing data and should not be rejected
    record = {"year": 2020, "temp_mean_celsius": 0, "precip_total_mm": 800, "source": "nasa"}
    assert validate_annual_record(record, "Test") is True


# ── global_sanity_check ───────────────────────────────────────────────────────

def test_global_sanity_check_clean():
    metrics = {"temp_trend_c_per_decade": 0.3, "precip_trend_pct_per_decade": -5.0}
    result  = global_sanity_check(metrics, "Test")
    assert "sanity_flags" not in result
    assert result.get("confidence_penalty", 0) == 0


def test_global_sanity_check_flags_outlier():
    metrics = {"temp_trend_c_per_decade": 5.0}  # outside [-1.5, 1.5]
    result  = global_sanity_check(metrics, "Test")
    assert "sanity_flags" in result
    assert len(result["sanity_flags"]) >= 1
    assert result["confidence_penalty"] >= 15


def test_global_sanity_check_multiple_flags():
    metrics = {
        "temp_trend_c_per_decade": 5.0,
        "precip_trend_pct_per_decade": 99.0,
    }
    result = global_sanity_check(metrics, "Test")
    assert result["confidence_penalty"] == len(result["sanity_flags"]) * 15


# ── validate_final_result ─────────────────────────────────────────────────────

def _good_result(**overrides):
    base = {
        "risk_score":        65,
        "executive_summary": "A" * 120,
        "recommendations":   [{"rank": 1, "action": "Reduce emissions"}],
        "confidence_score":  80,
        "hitl_required":     False,
        "hitl_reasons":      [],
    }
    base.update(overrides)
    return base


def test_validate_final_result_clean():
    result = validate_final_result(_good_result(), "Test")
    assert "data_quality_issues" not in result
    assert result["hitl_required"] is False
    assert result["confidence_score"] == 80


def test_validate_final_result_zero_score():
    # 1 issue → penalty=20, confidence = max(80-20, 30) = 60
    result = validate_final_result(_good_result(risk_score=0), "Test")
    assert result["hitl_required"] is True
    assert any("zero" in i for i in result["data_quality_issues"])
    assert result["confidence_score"] < 80   # penalised
    assert result["confidence_score"] >= 30  # never below floor


def test_validate_final_result_short_summary():
    # 1 issue → penalty=20, confidence = max(80-20, 30) = 60
    result = validate_final_result(_good_result(executive_summary="Too short."), "Test")
    assert result["hitl_required"] is True
    assert any("summary" in i for i in result["data_quality_issues"])
    assert result["confidence_score"] < 80
    assert result["confidence_score"] >= 30


def test_validate_final_result_no_recs():
    result = validate_final_result(_good_result(recommendations=[]), "Test")
    assert result["hitl_required"] is True
    assert any("recommendation" in i for i in result["data_quality_issues"])


def test_validate_final_result_multiple_issues_caps_confidence():
    # 3 issues → penalty=60, confidence = max(80-60, 30) = 30
    result = validate_final_result(
        _good_result(risk_score=0, executive_summary="Short.", recommendations=[]),
        "Test",
    )
    assert len(result["data_quality_issues"]) == 3
    assert result["confidence_score"] == 30


def test_validate_final_result_preserves_hitl_from_prior_step():
    # Existing hitl_reasons are preserved and new issues appended
    result = validate_final_result(
        _good_result(risk_score=0, hitl_required=True, hitl_reasons=["existing reason"]),
        "Test",
    )
    assert result["hitl_required"] is True
    assert any("existing reason" in r for r in result["hitl_reasons"])
    assert any("zero" in r for r in result["hitl_reasons"])


def test_validate_final_result_confidence_floor():
    # Even with zero starting confidence and 3 issues, floor is 30
    result = validate_final_result(
        _good_result(risk_score=0, executive_summary="x", recommendations=[], confidence_score=0),
        "Test",
    )
    assert result["confidence_score"] == 30


def test_validate_final_result_limited_nasa_warning():
    # < 5 NASA records triggers a warning but not HITL
    records = [{"year": y, "source": "nasa"} for y in range(2020, 2023)]  # 3 records
    result = validate_final_result(_good_result(), "Test", annual_records=records)
    assert result["hitl_required"] is False
    assert result["confidence_score"] < 80  # warning penalty applied
    assert any("Limited NASA" in r for r in result["hitl_reasons"])


# ── IMPOSSIBLE_VALUES coverage ────────────────────────────────────────────────

def test_impossible_values_covers_key_fields():
    required = {"temp_mean_celsius", "precip_total_mm", "temp_trend_c_per_decade"}
    assert required.issubset(set(IMPOSSIBLE_VALUES.keys()))


if __name__ == "__main__":
    for loc in KNOWN_GOOD:
        result = run_climate_engine_for(loc)
        exp    = loc["expected"]
        temp, precip, risk = result["temp_mean"], result["precip_mean"], result["risk_score"]
        t_ok = exp["temp_range"][0] <= temp <= exp["temp_range"][1]
        p_ok = exp["precip_range"][0] <= precip <= exp["precip_range"][1]
        r_ok = exp["risk_range"][0] <= risk <= exp["risk_range"][1]
        status = "✅" if (t_ok and p_ok and r_ok) else "❌"
        print(f"{status} {loc['region']}: temp={temp}°C precip={precip}mm risk={risk}")
