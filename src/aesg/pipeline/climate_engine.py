"""Deterministic climate risk engine. No LLM — pure arithmetic."""


def calculate_climate_risk(annual_records: list) -> dict:
    """Deterministic climate risk calculation. No LLM."""
    if not annual_records:
        return {}

    temps   = [r.get("temp_mean_celsius") or r.get("temp_mean_c") or 0 for r in annual_records]
    precips = [r.get("precip_total_mm") or 0 for r in annual_records]
    solars  = [r.get("solar_mean_kwh_m2") or 0 for r in annual_records]
    et0s    = [r.get("evapotranspiration_mm") or 0 for r in annual_records]
    years   = [r.get("year") or 0 for r in annual_records]
    n = len(annual_records)

    def linear_trend(values):
        if len(values) < 2:
            return 0
        x = list(range(len(values)))
        mx, my = sum(x) / len(x), sum(values) / len(values)
        num = sum((x[i] - mx) * (values[i] - my) for i in range(len(x)))
        den = sum((x[i] - mx) ** 2 for i in range(len(x)))
        return (num / den * 10) if den else 0  # per decade

    temp_trend   = linear_trend(temps)
    precip_trend = linear_trend(precips)
    solar_trend  = linear_trend(solars)

    # Baseline (first 3y) vs recent (last 3y)
    b_temp    = sum(temps[:3]) / 3    if len(temps) >= 3   else temps[0]
    r_temp    = sum(temps[-3:]) / 3   if len(temps) >= 3   else temps[-1]
    b_precip  = sum(precips[:3]) / 3  if len(precips) >= 3 else precips[0]
    r_precip  = sum(precips[-3:]) / 3 if len(precips) >= 3 else precips[-1]

    temp_change       = r_temp - b_temp
    precip_change_pct = ((r_precip - b_precip) / b_precip * 100) if b_precip else 0

    # Anomaly detection (>1.5 std dev)
    mean_t = sum(temps) / n
    std_t  = (sum((t - mean_t) ** 2 for t in temps) / n) ** 0.5
    mean_p = sum(precips) / n
    std_p  = (sum((p - mean_p) ** 2 for p in precips) / n) ** 0.5

    anomaly_years = [
        years[i] for i in range(n)
        if (std_t and abs(temps[i] - mean_t) > 1.5 * std_t)
        or (std_p and abs(precips[i] - mean_p) > 1.5 * std_p)
    ]
    hottest_year = years[temps.index(max(temps))]     if temps   else None
    driest_year  = years[precips.index(min(precips))] if precips else None

    # ET0 water deficit
    avg_et0    = sum(et0s[-3:]) / 3    if et0s and len(et0s) >= 3 else (et0s[-1] if et0s else 0)
    avg_precip = sum(precips[-3:]) / 3 if len(precips) >= 3       else r_precip
    et0_ratio  = avg_et0 / avg_precip if avg_precip > 0 else 0
    water_deficit = et0_ratio > 1.3

    # Risk scores (0-100)
    drought_score = min(100, max(0,
        max(0, -precip_change_pct) * 2
        + temp_change * 10
        + (30 if water_deficit else 0)
        + len(anomaly_years) * 3
    ))
    heat_stress_score = min(100, max(0,
        temp_trend * 20
        + temp_change * 15
        + len(anomaly_years) * 4
    ))
    flood_score = min(100, max(0,
        max(0, precip_change_pct) * 1.5
        + (20 if std_p > mean_p * 0.3 else 0)
    ))

    # Urgency
    max_score = max(drought_score, heat_stress_score, flood_score)
    if max_score > 70:
        urgency = "CRITICAL"
    elif max_score > 45:
        urgency = "HIGH"
    elif max_score > 25:
        urgency = "MEDIUM"
    else:
        urgency = "LOW"

    return {
        # Trends
        "temp_trend_c_per_decade":     round(temp_trend, 3),
        "precip_trend_pct_per_decade": round(precip_trend, 3),
        "solar_trend":                 round(solar_trend, 3),
        # Changes
        "temp_change_label": (
            f"{temp_change:+.2f}°C vs baseline "
            f"({b_temp:.2f}°C → {r_temp:.2f}°C)"
        ),
        "precip_change_label": (
            f"{precip_change_pct:+.1f}% vs baseline "
            f"({b_precip:.1f}mm → {r_precip:.1f}mm)"
        ),
        # Anomalies
        "hottest_year":  hottest_year,
        "driest_year":   driest_year,
        "anomaly_years": anomaly_years,
        # Scores
        "drought_score":     round(drought_score, 1),
        "heat_stress_score": round(heat_stress_score, 1),
        "flood_score":       round(flood_score, 1),
        # Water
        "water_deficit":    water_deficit,
        "et0_precip_ratio": round(et0_ratio, 2),
        # For agents
        "compliance_urgency": urgency,
        "compliance_exposure": (
            "CSRD · ISSB S2 · EU Taxonomy"
            if urgency in ["HIGH", "CRITICAL"]
            else "CSRD · ISSB S2"
        ),
    }
