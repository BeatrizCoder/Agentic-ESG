# Sector-Specific Risk Profiles

This directory contains YAML configuration files that define sector-specific climate risk thresholds, compliance frameworks, and key risks for Agentic ESG analysis.

## Overview

Each sector has unique climate risk sensitivities and regulatory priorities. These profiles allow the ESG analysis pipeline to:

1. **Apply sector-specific risk thresholds** - Different sectors have different tolerances for drought, heat stress, and flood risks
2. **Prioritize relevant frameworks** - Focus on the most applicable ESG frameworks (CSRD, ISSB S2, EU Taxonomy)
3. **Identify key sector risks** - Highlight climate risks most relevant to each industry
4. **Tailor recommendations** - Generate sector-appropriate action plans

## Available Sectors

| Sector | File | Key Focus Areas |
|--------|------|-----------------|
| General | `general.yaml` | Baseline thresholds for all sectors |
| Agriculture & Food | `agriculture_food.yaml` | Water availability, crop yields, soil health |
| Real Estate | `real_estate.yaml` | Flood damage, asset resilience, cooling systems |
| Finance & Banking | `finance_banking.yaml` | Portfolio risk, financed emissions, stranded assets |
| Infrastructure | `infrastructure.yaml` | Flood resilience, material stress, maintenance costs |
| Manufacturing | `manufacturing.yaml` | Water for production, supply chain, equipment stress |
| Energy & Utilities | `energy_utilities.yaml` | Cooling water, grid resilience, renewable output |
| Retail & Logistics | `retail_logistics.yaml` | Supply chain, cold chain, transportation routes |

## YAML Structure

Each sector profile contains:

```yaml
sector: "Sector Display Name"

risk_thresholds:
  drought_critical: 40    # Score above which drought becomes CRITICAL
  heat_critical: 45       # Score above which heat stress becomes CRITICAL
  flood_critical: 35      # Score above which flood becomes CRITICAL

primary_frameworks:
  - "CSRD ESRS E1 (climate change)"
  - "CSRD ESRS E3 (water)"
  - "ISSB S2"

key_risks:
  - "Sector-specific risk 1"
  - "Sector-specific risk 2"
  - "Sector-specific risk 3"

focus_articles:
  - "ESRS E3-4 water consumption"
  - "ISSB S2 paragraph 10b"

recommendation_tone: "sector operations context"
```

## Risk Thresholds

Lower thresholds = higher sensitivity to that risk type.

**Example: Agriculture & Food**
- `drought_critical: 40` - Agriculture is highly sensitive to drought
- `heat_critical: 45` - Moderate sensitivity to heat stress
- `flood_critical: 35` - High sensitivity to flooding (crop damage)

**Example: Finance & Banking**
- `drought_critical: 48` - Lower direct sensitivity to drought
- `heat_critical: 48` - Lower direct sensitivity to heat
- `flood_critical: 38` - Moderate sensitivity (branch operations)

## Usage

### In Python Code

```python
from aesg.sectors import load_sector_profile, get_sector_context

# Load a sector profile
config = load_sector_profile("agriculture")
thresholds = config["risk_thresholds"]
frameworks = config["primary_frameworks"]

# Get formatted context for agent prompts
context = get_sector_context("Agriculture & Food")
```

### In the Pipeline

The orchestrator automatically loads sector profiles:

```python
# In orchestrator.py
sector_config = load_sector_profile(sector)
sector_thresholds = sector_config.get("risk_thresholds", {})

# Pass to climate engine
climate_metrics = calculate_climate_risk(
    unified_records, 
    sector_thresholds
)
```

### In ESG Strategist

The ESG Strategist agent receives sector context:

```python
# In tasks.py
sector_context = get_sector_context(sector)

# Included in agent prompt
description = f"""
{sector_context}

CLIMATE FINDINGS:
{climate_summary}
...
"""
```

## Adding New Sectors

1. Create a new YAML file in this directory (e.g., `healthcare.yaml`)
2. Follow the structure shown above
3. Add sector mapping to `__init__.py`:

```python
SECTOR_MAPPING = {
    # ... existing mappings ...
    "healthcare": "healthcare",
    "health": "healthcare",
}
```

4. The sector will be automatically available in the API

## Sector Mapping

The loader supports flexible sector name matching:

- `"agriculture"` → `agriculture_food.yaml`
- `"Agriculture & Food"` → `agriculture_food.yaml`
- `"food"` → `agriculture_food.yaml`
- `"real estate"` → `real_estate.yaml`
- `"property"` → `real_estate.yaml`

See `SECTOR_MAPPING` in `__init__.py` for all aliases.

## Integration Points

### 1. Climate Risk Engine (`climate_engine.py`)

Uses sector thresholds to determine urgency:

```python
is_critical = (
    drought_score > thresholds["drought_critical"] or
    heat_stress_score > thresholds["heat_critical"] or
    flood_score > thresholds["flood_critical"]
)
```

### 2. ESG Strategist Agent (`tasks.py`)

Receives sector context including:
- Risk thresholds
- Primary frameworks
- Key sector-specific risks
- Focus articles for compliance mapping

### 3. API Routes (`api/routes.py`)

Accepts `sector` parameter in analysis requests:

```json
{
  "latitude": -15.7801,
  "longitude": -47.9292,
  "sector": "Agriculture & Food"
}
```

## Framework References

### CSRD (Corporate Sustainability Reporting Directive)
- **ESRS E1**: Climate change
- **ESRS E3**: Water and marine resources
- **ESRS E4**: Biodiversity and ecosystems

### ISSB S2 (Climate-related Disclosures)
- **Paragraph 10**: Physical and transition risks
- **Paragraph 10a**: Acute physical risks
- **Paragraph 10b**: Chronic physical risks
- **Paragraph 14**: Asset resilience
- **Paragraph 29**: Scenario analysis

### EU Taxonomy
- **Article 8**: Disclosure requirements
- **Article 10**: Substantial contribution criteria
- **CCA Annex II**: Climate change adaptation screening
- **DNSH**: Do No Significant Harm criteria

## Best Practices

1. **Threshold Calibration**: Lower thresholds for sectors with higher climate sensitivity
2. **Framework Priority**: List 2-4 most relevant frameworks for each sector
3. **Risk Specificity**: Include 4-6 concrete, sector-specific climate risks
4. **Article Precision**: Reference specific articles/paragraphs when possible
5. **Tone Consistency**: Use sector-appropriate language in recommendation_tone

## Testing

Test sector profile loading:

```python
from aesg.sectors import list_available_sectors, load_sector_profile

# List all sectors
sectors = list_available_sectors()
print(sectors)

# Test loading each sector
for sector in sectors:
    config = load_sector_profile(sector)
    print(f"{config['sector']}: {config['risk_thresholds']}")
```

## Maintenance

- Review thresholds quarterly based on analysis results
- Update framework references when regulations change
- Add new sectors as client needs evolve
- Keep focus_articles aligned with latest regulatory guidance