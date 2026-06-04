# Sector-Specific Risk Profiles Implementation

## Overview

This document describes the implementation of custom sector risk profiles for Agentic ESG, enabling tailored climate risk analysis for different industries.

## Implementation Summary

### 1. Created Sector Configuration Files

**Location:** `src/aesg/sectors/`

Eight YAML configuration files were created, each defining sector-specific parameters:

- `general.yaml` - Baseline configuration for all sectors
- `agriculture_food.yaml` - Agriculture & Food industry
- `real_estate.yaml` - Real Estate & Property
- `finance_banking.yaml` - Finance & Banking
- `infrastructure.yaml` - Infrastructure
- `manufacturing.yaml` - Manufacturing
- `energy_utilities.yaml` - Energy & Utilities
- `retail_logistics.yaml` - Retail & Logistics

**YAML Structure:**
```yaml
sector: "Sector Display Name"
risk_thresholds:
  drought_critical: 40    # Lower = more sensitive
  heat_critical: 45
  flood_critical: 35
primary_frameworks:
  - "CSRD ESRS E3 (water)"
  - "ISSB S2"
key_risks:
  - "Sector-specific risk 1"
  - "Sector-specific risk 2"
focus_articles:
  - "ESRS E3-4 water consumption"
  - "ISSB S2 paragraph 10b"
recommendation_tone: "sector operations context"
```

### 2. Created Sector Loader Module

**File:** `src/aesg/sectors/__init__.py`

**Key Functions:**
- `load_sector_profile(sector: str)` - Load YAML configuration for a sector
- `get_sector_context(sector: str)` - Generate formatted context for agent prompts
- `list_available_sectors()` - List all available sector profiles
- `SECTOR_MAPPING` - Dictionary mapping sector aliases to file names

**Features:**
- Flexible sector name matching (e.g., "agriculture", "Agriculture & Food", "food" all map to `agriculture_food.yaml`)
- Automatic fallback to `general.yaml` if sector not found
- Error handling with logging

### 3. Updated Climate Risk Engine

**File:** `src/aesg/pipeline/climate_engine.py`

**Changes:**
- Added `sector_thresholds` parameter to `calculate_climate_risk()`
- Modified urgency calculation to use sector-specific critical thresholds
- Maintains backward compatibility with default thresholds

**Logic:**
```python
is_critical = (
    drought_score > thresholds["drought_critical"] or
    heat_stress_score > thresholds["heat_critical"] or
    flood_score > thresholds["flood_critical"]
)
```

### 4. Updated ESG Strategist Agent

**File:** `src/aesg/agents/tasks.py`

**Changes:**
- Modified `make_esg_strategy_task()` to load and inject sector context
- Agent prompt now includes:
  - Sector-specific risk thresholds
  - Primary frameworks for the sector
  - Key sector-specific climate risks
  - Focus articles for compliance mapping
  - Recommendation tone guidance

**Example Context Injection:**
```python
from ..sectors import get_sector_context

sector_context = get_sector_context(sector)

description = f"""
{sector_context}

CLIMATE FINDINGS:
{climate_summary}
...
"""
```

### 5. Integrated into Pipeline Orchestrator

**File:** `src/aesg/pipeline/orchestrator.py`

**Changes in `run_analysis()`:**
- Loads sector profile at the start of Step 2a
- Extracts risk thresholds from sector configuration
- Passes thresholds to `calculate_climate_risk()`
- Logs sector-specific threshold values

**Changes in `run_comparison_pipeline()`:**
- Also loads sector profile and passes thresholds
- Ensures consistency across all pipeline modes

### 6. Added API Endpoint

**File:** `src/aesg/api/routes.py`

**New Endpoint:**
```
GET /api/sectors
```

**Response:**
```json
{
  "sectors": [
    "Agriculture & Food",
    "Energy & Utilities",
    "Finance & Banking",
    ...
  ],
  "aliases": {
    "agriculture": "agriculture_food",
    "food": "agriculture_food",
    ...
  },
  "count": 8
}
```

### 7. Updated Dependencies

**File:** `requirements.txt`

Added `pyyaml>=6.0.0` for YAML parsing.

### 8. Documentation

**Files:**
- `src/aesg/sectors/README.md` - Comprehensive documentation of sector profiles
- `SECTOR_PROFILES_IMPLEMENTATION.md` - This implementation summary

## How It Works

### Request Flow

1. **API Request** - Client sends analysis request with `sector` parameter:
   ```json
   {
     "latitude": -15.7801,
     "longitude": -47.9292,
     "sector": "Agriculture & Food",
     "start_year": 2014,
     "end_year": 2023
   }
   ```

2. **Orchestrator** - Loads sector profile:
   ```python
   sector_config = load_sector_profile("Agriculture & Food")
   sector_thresholds = {
     "drought_critical": 40,
     "heat_critical": 45,
     "flood_critical": 35
   }
   ```

3. **Climate Engine** - Applies sector thresholds:
   ```python
   climate_metrics = calculate_climate_risk(
       unified_records, 
       sector_thresholds
   )
   # Agriculture becomes CRITICAL at drought_score > 40
   # (vs. General sector at > 45)
   ```

4. **ESG Strategist** - Receives sector context:
   ```
   SECTOR: Agriculture & Food
   
   SECTOR-SPECIFIC RISK THRESHOLDS:
   - Drought becomes CRITICAL when score > 40
   - Heat stress becomes CRITICAL when score > 45
   
   PRIMARY FRAMEWORKS FOR THIS SECTOR:
   - CSRD ESRS E3 (water)
   - CSRD ESRS E4 (biodiversity)
   - ISSB S2
   
   KEY SECTOR-SPECIFIC CLIMATE RISKS:
   - Crop yield reduction from drought
   - Irrigation water availability
   - Supply chain disruption
   - Soil degradation
   ```

5. **Response** - Analysis includes sector-tailored insights

## Key Benefits

### 1. Sector-Specific Sensitivity
- Agriculture triggers CRITICAL at drought_score > 40
- Finance triggers CRITICAL at drought_score > 48
- Reflects real-world industry vulnerabilities

### 2. Relevant Framework Prioritization
- Agriculture focuses on ESRS E3 (water) and E4 (biodiversity)
- Finance focuses on financed emissions and scenario analysis
- Real Estate focuses on physical asset resilience

### 3. Tailored Risk Identification
- Agriculture: "Crop yield reduction from drought"
- Manufacturing: "Water availability for production"
- Retail: "Supply chain disruption from extreme weather"

### 4. Precise Compliance Mapping
- Agriculture: ESRS E3-4 (water consumption), ESRS E4-6 (biodiversity)
- Finance: ESRS E1-9 (financed emissions), ISSB S2 paragraph 29
- Infrastructure: EU Taxonomy CCA screening criteria

## Example: Agriculture vs. General Sector

### Scenario
- Location: Brasília, Brazil
- Drought score: 42
- Heat stress score: 38
- Flood score: 25

### General Sector (default thresholds)
- Drought: 42 < 45 → **HIGH** risk
- Heat: 38 < 50 → **MEDIUM** risk
- Overall urgency: **HIGH**

### Agriculture Sector (sensitive thresholds)
- Drought: 42 > 40 → **CRITICAL** risk ✓
- Heat: 38 < 45 → **HIGH** risk
- Overall urgency: **CRITICAL**

### Result
Agriculture sector correctly identifies CRITICAL urgency due to lower drought threshold, triggering:
- Immediate compliance obligations
- Priority framework: CSRD ESRS E3 (water)
- Specific risks: "Irrigation water availability", "Crop yield reduction"

## Testing

### Manual Testing

```python
# Test sector loading
from aesg.sectors import load_sector_profile, list_available_sectors

sectors = list_available_sectors()
print(f"Available sectors: {sectors}")

config = load_sector_profile("agriculture")
print(f"Thresholds: {config['risk_thresholds']}")
```

### API Testing

```bash
# List available sectors
curl http://localhost:8000/api/sectors

# Run analysis with sector
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{
    "latitude": -15.7801,
    "longitude": -47.9292,
    "region_label": "Brasília",
    "sector": "Agriculture & Food",
    "start_year": 2014,
    "end_year": 2023
  }'
```

## Future Enhancements

### 1. Additional Sectors
- Healthcare
- Technology
- Transportation
- Mining & Extraction
- Hospitality & Tourism

### 2. Dynamic Threshold Calibration
- Machine learning to optimize thresholds based on historical analysis results
- Regional threshold adjustments (e.g., Mediterranean agriculture vs. tropical)

### 3. Sector-Specific Metrics
- Agriculture: Crop-specific water requirements
- Energy: Cooling degree days
- Real Estate: Building energy performance

### 4. Multi-Sector Analysis
- Support for companies operating across multiple sectors
- Weighted risk aggregation

### 5. Regulatory Updates
- Automated framework reference updates
- Version tracking for compliance articles

## Maintenance

### Adding a New Sector

1. Create YAML file in `src/aesg/sectors/`:
   ```yaml
   sector: "New Sector"
   risk_thresholds:
     drought_critical: 45
     heat_critical: 48
     flood_critical: 38
   primary_frameworks:
     - "CSRD ESRS E1"
   key_risks:
     - "Risk 1"
   focus_articles:
     - "Article reference"
   recommendation_tone: "sector context"
   ```

2. Add mapping to `src/aesg/sectors/__init__.py`:
   ```python
   SECTOR_MAPPING = {
       # ... existing mappings ...
       "new sector": "new_sector",
       "newsector": "new_sector",
   }
   ```

3. Test:
   ```python
   from aesg.sectors import load_sector_profile
   config = load_sector_profile("new sector")
   ```

### Updating Thresholds

1. Review analysis results for the sector
2. Adjust thresholds in the YAML file
3. Document rationale in git commit message
4. Test with representative locations

### Updating Framework References

1. Monitor regulatory changes (CSRD, ISSB, EU Taxonomy)
2. Update `focus_articles` in relevant sector YAMLs
3. Update `src/aesg/sectors/README.md` framework reference section

## Files Modified

- `src/aesg/sectors/__init__.py` (created)
- `src/aesg/sectors/general.yaml` (created)
- `src/aesg/sectors/agriculture_food.yaml` (created)
- `src/aesg/sectors/real_estate.yaml` (created)
- `src/aesg/sectors/finance_banking.yaml` (created)
- `src/aesg/sectors/infrastructure.yaml` (created)
- `src/aesg/sectors/manufacturing.yaml` (created)
- `src/aesg/sectors/energy_utilities.yaml` (created)
- `src/aesg/sectors/retail_logistics.yaml` (created)
- `src/aesg/sectors/README.md` (created)
- `src/aesg/pipeline/climate_engine.py` (modified)
- `src/aesg/pipeline/orchestrator.py` (modified)
- `src/aesg/agents/tasks.py` (modified)
- `src/aesg/api/routes.py` (modified)
- `requirements.txt` (modified)

## Backward Compatibility

All changes maintain backward compatibility:
- Default sector is "General" if not specified
- Climate engine uses default thresholds if `sector_thresholds=None`
- Existing API requests without `sector` parameter continue to work
- No breaking changes to response format

## Conclusion

The sector-specific risk profiles implementation enables Agentic ESG to provide more accurate, relevant, and actionable climate risk analysis tailored to each industry's unique vulnerabilities and regulatory requirements.