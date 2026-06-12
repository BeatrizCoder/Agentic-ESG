# Agentic ESG — Climate Risk Intelligence for ESG & Compliance

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green?logo=fastapi)](https://fastapi.tiangolo.com)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-purple)](https://crewai.com)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue)](LICENSE)
[![Railway](https://img.shields.io/badge/Deploy-Railway-black?logo=railway)](https://railway.app)
[![Security: bandit](https://img.shields.io/badge/security-bandit-yellow.svg)](https://github.com/PyCQA/bandit)
[![LGPD Compliant](https://img.shields.io/badge/LGPD-compliant-brightgreen.svg)](SECURITY.md)
[![EU AI Act](https://img.shields.io/badge/EU%20AI%20Act-Art.%2013-blue.svg)](SECURITY.md)

> Physical climate risk assessment powered by NASA satellite data, IPCC projections, and Claude AI agents.

📦 **GitHub:** https://github.com/BeatrizCoder/agentic-esg

---

## 🌐 Live Demo

**[agentic-esg-production.up.railway.app](https://agentic-esg-production.up.railway.app)**

> Try it: type any city name and get a full ESG climate risk analysis powered by real NASA data.

---

## Overview

Organizations face mounting regulatory pressure to assess and disclose physical climate risks under CSRD, ISSB S2, and the EU Taxonomy.

**Agentic ESG** provides a fast, data-driven starting point for climate risk intelligence. It combines NASA satellite observations, ERA5 climate reanalysis, and IPCC climate projections through a multi-agent AI architecture to deliver executive-ready climate risk assessments in under 30 seconds (NASA-only analyses) or up to 3–5 minutes when IPCC projections are included.

> ⚠️ **Important Disclaimer** **Agentic ESG** is a **decision-support system**, not a substitute for professional climate risk advisory, legal interpretation, or regulatory reporting. All outputs include a confidence score and should be reviewed by qualified subject matter experts before being used in investment decisions, sustainability disclosures, or regulatory filings.

Agentic ESG maps physical climate risks to:

- **CSRD (ESRS E1)**
- **ISSB S2**
- **EU Taxonomy**

By translating climate observations and projections into compliance-aware business intelligence, the platform helps ESG analysts, sustainability teams, risk managers, and investment professionals accelerate climate risk screening, double-materiality assessments, and early-stage compliance evaluations.

---

## Architecture

![Agentic ESG Architecture](architecture.svg)

---

## The Problem

Organizations face mounting pressure to assess and disclose physical climate risks:

- **CSRD (Corporate Sustainability Reporting Directive)** — EU companies must report climate risks under ESRS E1 by 2024-2025
- **ISSB S2 (Climate-related Disclosures)** — Global standard requiring scenario analysis and physical risk assessment
- **EU Taxonomy** — Investment screening requires climate risk evaluation for sustainable finance classification
- **Traditional assessments** — Manual climate risk analysis costs $5,000-$50,000 and takes weeks

Agentic ESG delivers executive-ready climate risk assessment in ~$0.04 per location.

---

## How It Works

### The Pipeline (6-Step Sequential Architecture)

```
Location Input (lat/lon)
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 1: Data Collector (Python adapter — no LLM)         │
│   • NASA POWER API: historical satellite data 1981-2025  │
│   • ERA5 reanalysis: current-year real observations      │
│   • OpenMeteo IPCC: Climate projections 2027-2050        │
│   • 5 parameters: temp, precip, solar, ET0, soil moist. │
│   • All three sources fetched in parallel                 │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 2a: Climate Risk Engine (Python — no LLM)           │
│   • OLS trend analysis per decade (temp, precip, solar)  │
│   • Drought / heat stress / flood sub-scores             │
│   • Sector-specific risk thresholds                       │
│   • Sanity check: rejects physically impossible values   │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 2b: Climate Interpreter (Claude Haiku 4.5)          │
│   • Synthesises climate metrics into executive language  │
│   • Identifies anomalies: extreme years, heat stress     │
│   • Highlights drought, flood, and heat risk context     │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 3: ESG Strategist (Claude Sonnet 4.6)               │
│   • Maps risks to CSRD ESRS E1 articles                  │
│   • Evaluates ISSB S2 scenario requirements              │
│   • Assesses EU Taxonomy climate criteria                │
│   • Determines compliance urgency                         │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 4: Report Writer (Claude Sonnet 4.6)                │
│   • Generates executive summary                           │
│   • Calculates physical risk score (0-100)               │
│   • Assigns investment status badge                       │
│   • Provides framework-specific recommendations          │
│   • Defines ecosystem offset targets                      │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Step 5: Quality Judge (Claude Sonnet 4.6)                │
│   • Validates output coherence                            │
│   • Flags inconsistencies across agent outputs            │
│   • Assigns confidence score (0-100)                      │
│   • ⚠️ SKIPPED for projection analyses (end_year > 2025) │
│     → confidence defaults to 65, HITL always triggered   │
└───────────────────────────────────────────────────────────┘
        ↓
    Final Report
```

> **Comparison mode** (`/api/analyze/compare`) runs a lightweight pipeline of Steps 1 + 2a + 2b only — no ESG Strategist, Report Writer, or Quality Judge. It is NASA-only (no projections) and limited to 5 requests/hour.

### Data Sources

**NASA POWER API (1981–2025)**
- Real satellite observations from NASA's POWER project
- Daily resolution: temperature (T2M), precipitation (PRECTOTCORR), solar irradiance (ALLSKY_SFC_SW_DWN), FAO-56 evapotranspiration (ET0_FAO), soil moisture 0–10 cm (SOIL_MOISTURE_0_10CM)
- Global coverage at 0.5° × 0.5° resolution
- Aggregated to annual statistics for trend analysis

**OpenMeteo ERA5 (2026–present)**
- Real observed data from ECMWF ERA5 reanalysis for the current and recent years
- Bridges the gap between NASA POWER history and IPCC projections
- Same 5-parameter coverage as NASA POWER

**OpenMeteo IPCC Climate API (2027–2050)**
- IPCC AR6 climate projections using a 5-model ensemble (CMCC_CM2_VHR4, MRI_AGCM3_2_S, EC_Earth3P_HR, MPI_ESM1_2_XR, NICAM16_8S)
- Three emissions scenarios: SSP1-2.6 (optimistic), SSP2-4.5 (moderate), SSP5-8.5 (high)
- Daily resolution: temperature, precipitation, evapotranspiration (ET0)
- Enables long-term risk forecasting across scenario space

### Agent Details

| Component | Step | Type | Tokens | Role |
|-----------|------|------|--------|------|
| Data Collector | 1 | Python | 0 | Fetches NASA + OpenMeteo in parallel |
| Climate Risk Engine | 2a | Python | 0 | OLS trends, sub-scores, anomalies |
| Climate Interpreter | 2b | Claude Haiku 4.5 | ~200 | Narrative synthesis |
| ESG Strategist | 3 | Claude Sonnet 4.6 | ~1,200 | CSRD/ISSB/EU Taxonomy mapping |
| Report Writer | 4 | Claude Sonnet 4.6 | ~1,500 | Executive report + risk score |
| Quality Judge | 5 | Claude Sonnet 4.6 | ~1,000 | Validation + confidence score |

Hybrid design: deterministic Python engine handles quantitative risk calculation (zero tokens, fully auditable), LLMs only where language reasoning adds measurable value. Quality Judge is skipped for analyses that include climate projections (end_year > 2025) to avoid timeout — those analyses always receive a HITL flag.

---

## Key Features

### Risk Assessment
- **Physical Climate Risk Score (0-100)** — Quantitative measure of location-specific climate exposure
- **Investment Status Badge** — Approved / Conditioned / Restricted / Suspended (based on risk thresholds), translated in all 5 languages
- **Risk Level Classification** — Low / Medium / High / Critical
- **Trend Analysis** — Temperature, precipitation, and ET0 changes per decade
- **Anomaly Detection** — Identifies extreme years (hottest, driest, wettest)

### Enhanced Climate Data (5 Parameters)
- **Temperature** — Mean annual (T2M) from NASA POWER satellite observations
- **Precipitation** — Total annual (PRECTOTCORR), corrected for systematic bias
- **Solar Radiation** — Surface shortwave downwelling (ALLSKY_SFC_SW_DWN, kWh/m²/day)
- **Evapotranspiration (ET0)** — FAO-56 Penman-Monteith reference ET; ET0/precipitation ratio > 1.3 flagged as HIGH water deficit (CSRD ESRS E3-4)
- **Soil Moisture** — 0–10 cm layer (m³/m³); declining trend flags long-term desiccation risk

### Three-Source Climate Timeline
- **NASA POWER** — Verified historical observations 1981–2025
- **OpenMeteo ERA5** — Real observed data 2026–present (ECMWF reanalysis)
- **OpenMeteo IPCC** — Climate projections 2027–2050 (SSP1-2.6, SSP2-4.5, SSP5-8.5)
- Unified visualization showing all three sources with clear source labels

### ESG Compliance Mapping
- **CSRD ESRS E1** — Article-level mapping (E1-1 through E1-9) with exposure assessment
- **ISSB S2** — Scenario analysis requirements and disclosure recommendations
- **EU Taxonomy** — Climate adaptation criteria evaluation (Annex I, Appendix A)
- **Double Materiality Assessment** — Impact and financial materiality per CSRD ESRS 1
- **Compliance Urgency** — Low / Medium / High / Critical priority classification

### Batch Analysis
- **CSV Upload** — Analyze up to **5 regions** in a single submission
- **Template Download** — Pre-formatted CSV with example rows (region, lat, lon, sector, scenario, optional compare years)
- **Sequential Processing** — 2-second delay between regions to respect NASA API rate limits
- **Comparison Mode in Batch** — Add `compare_start_year` / `compare_end_year` columns to run period comparisons per row
- **Results Table** — Risk score, risk level, investment status, and confidence for every region
- **Excel Export** — All batch results in a single formatted workbook, sorted by risk score
- **Rate limit:** 3 batch jobs per hour per IP

### Historical Comparison Mode
- **Dual-period analysis** — Compare climate risk between two time periods for the same location
- **Lightweight pipeline** — Runs Steps 1, 2a, 2b only (Data Collector + Climate Engine + Haiku); no full ESG report
- **NASA-only** — Uses historical observed data; does not include ERA5 or IPCC projections
- **Fixed-baseline scoring** — Historical period's mean temperature is used as the reference for both periods
- **Rate limit:** 5 comparisons per hour per IP

### Sector-Specific Risk Profiles
8 built-in sector profiles with tailored risk thresholds, compliance focus areas, and recommendation tone:

| Sector | Key Climate Risks |
|--------|------------------|
| General | All-risk baseline |
| Agriculture & Food | Drought, heat stress, soil moisture |
| Energy & Utilities | Heat demand shifts, solar variability |
| Finance & Banking | Physical asset exposure, stranded assets |
| Infrastructure | Flood, extreme heat, urban heat island |
| Manufacturing | Water stress, supply chain disruption |
| Real Estate | Flood risk, sea-level rise, heat |
| Retail & Logistics | Supply chain, warehouse flood/heat |

### ESG Glossary
- Multilingual glossary of key ESG and climate terms
- Supports English, Portuguese (PT-BR), German, French, and Spanish
- Searchable: CSRD, ISSB S2, EU Taxonomy, Double Materiality, HITL, SSP Scenarios, and more

### AI Transparency Layer (EU AI Act Art. 13)
- **Risk Score Composition** — Weighted factor breakdown showing what drove the score
- **Agent Reasoning Chain** — What each agent received as input and what it concluded
- **Validation Audit Trail** — Per-check results from the Quality Judge
- **Interpretability vs Explainability** — Separated score factors from narrative reasoning

### Human-in-the-Loop Flag
- Automatic flag when Quality Judge confidence falls below 70%
- Always triggered when analysis includes IPCC projections (end_year > 2025), because Quality Judge is skipped for those analyses
- Also triggers on: critical risk + low confidence, extreme data anomalies (>3σ), data quality issues, Quality Judge verdict "flagged" or "needs_review"
- Recommends expert validation before use in regulatory filings or investment decisions

### Ecosystem Offsets
- **Science-Based Targets** — Reforestation, wetland restoration, mangrove protection
- **Quantified Requirements** — Hectares, carbon sequestration potential, biodiversity impact
- **Regional Adaptation** — Tailored to local ecosystem and climate conditions

### Multilingual Support
- English (EN), Portuguese / PT-BR (PT), Spanish (ES), French (FR), German (DE)
- All UI labels, risk badges, investment status, and the Analyze button translate dynamically
- Language preference saved in localStorage and restored on next visit

### Terms & Privacy
- Bilingual EN/PT Terms of Use and Privacy Policy (scroll-to-accept)
- Platform gated until both documents are accepted
- LGPD compliant session storage (anonymous 24h TTL cookies)
- © 2026 Beatriz Costa Leal

### User Experience
- **Session History** — MongoDB-backed analysis storage with 30-day TTL; last 10 analyses per session
- **Dark/Light Theme** — Automatic system preference detection + manual toggle
- **PDF & Excel Export** — Professional report generation with charts and tables
- **Interactive Map** — Leaflet.js map with click-to-analyze any location globally

---

## Tech Stack

### Backend
- **Framework:** FastAPI (Python 3.11)
- **AI Orchestration:** CrewAI (multi-agent framework)
- **LLM Provider:** Anthropic Claude (Haiku 4.5 + Sonnet 4.6)
- **HTTP Client:** httpx (async) with tenacity retry logic
- **Rate Limiting:** slowapi
- **Testing:** pytest with async support

### Data & APIs
- **Climate Data:** NASA POWER API v2.5 — temperature, precipitation, solar, ET0, soil moisture (free, no auth)
- **Recent Observations:** OpenMeteo ERA5 reanalysis — real observed data 2026+ (free, no auth)
- **Projections:** OpenMeteo IPCC Climate API — projections to 2050, 3 SSP scenarios (free, no auth)
- **Database:** MongoDB — hosted as a service on Railway (persistent volume, not ephemeral storage)

### Frontend
- **Stack:** Vanilla HTML/CSS/JavaScript (no framework)
- **Styling:** Custom CSS with glassmorphism effects
- **Charts:** Chart.js for data visualization
- **Maps:** Leaflet.js for interactive location selection

### Deployment
- **Backend:** Railway (Docker container)
- **Database:** MongoDB — hosted as a service on Railway (persistent volume, not ephemeral storage)
- **Frontend:** Served via FastAPI static files
- **Domain:** Custom domain via Railway

### Development Tools
- **Development Tools:** Built with Claude Code (Anthropic) for architecture and development. IBM Bob (watsonx Code Assistant) — AI assistant used for deployment configuration, documentation, and code review. Code architecture and business logic designed by Beatriz Costa Leal.
- **Version Control:** Git + GitHub
- **Environment:** WSL2 Ubuntu on Windows 11

---

## Auditability & Transparency

Agentic ESG is designed for auditability:

- **Data provenance:** NASA endpoint URL + OpenMeteo model identifier logged per analysis
- **Timestamp:** Exact analysis datetime recorded and stored
- **Agent execution trace:** Per-agent token consumption visible in the Data Sources tab
- **Confidence score:** Quality Judge scores each output 0–100, flags inconsistencies; defaults to 65 for projection analyses (judge skipped)
- **Session isolation:** Anonymous 24h TTL session cookies, LGPD compliant

All provenance data visible in the **Data Sources** tab of every analysis report.

---

## Cost Per Analysis

**~$0.04 per full analysis** (NASA-only, 4 LLM agents)

| Agent | Model | Avg Tokens | Avg Cost |
|-------|-------|-----------|---------|
| Data Collector | Python (no LLM) | 0 | $0.000 |
| Climate Risk Engine | Python (no LLM) | 0 | $0.000 |
| Climate Analyst | Haiku 4.5 | ~1,000 | $0.003 |
| ESG Strategist | Sonnet 4.6 | ~1,400 | $0.011 |
| Report Writer | Sonnet 4.6 | ~1,700 | $0.014 |
| Quality Judge | Sonnet 4.6 | ~1,100 | $0.009 |
| **Total** | | **~5,200** | **~$0.037** |

*Costs based on Anthropic pricing: Haiku 4.5 $0.25/$1.25 per MTok (in/out), Sonnet 4.6 $3/$15 per MTok (in/out)*

*Quality Judge is skipped for analyses including IPCC projections — cost is lower but HITL is always triggered.*

---

## Try These Locations

- São Paulo, Brazil: -23.5505, -46.6333
- Miami, USA: 25.7617, -80.1918
- Mumbai, India: 19.0760, 72.8777
- Amsterdam, Netherlands: 52.3676, 4.9041

---

## Architecture Details

### Adapter Pattern
The Data Collector (Step 1) is a **pure Python adapter** — no LLM involved. It:
1. Fetches raw JSON from NASA POWER and OpenMeteo APIs **in parallel** (asyncio.gather)
2. Normalizes data structures (handles missing values, unit conversions)
3. Aggregates daily observations into annual statistics
4. Serializes records into a compact JSON format for downstream agents

This design keeps data collection **fast, deterministic, and cost-free** (no LLM tokens).

### Sequential Agent Pipeline
Agents run **sequentially** (not in parallel) because each depends on the previous agent's output:
- Step 2b needs normalized data from Step 1
- Step 3 needs climate findings from Step 2b
- Step 4 needs both climate + compliance summaries
- Step 5 validates the entire chain (skipped for projection analyses)

**Total pipeline time:**
- NASA-only (1981–2025): ~25–35 seconds
- With ERA5 (2026): ~30–45 seconds
- With IPCC projections (2027–2050): ~2–5 minutes (Quality Judge skipped)
- **Server timeout:** 300 seconds (5 minutes)

### Token Optimization
- **Compact summaries:** Each agent receives only the fields it needs (not full raw data)
- **JSON serialization:** Structured output parsing with fallback to regex extraction
- **Silent execution:** CrewAI console output suppressed to avoid TTY errors on servers

---

## Data Quality & Validation

Agentic ESG implements a three-layer data quality protection system:

### Layer 1 — Input Validation
All raw data from NASA POWER and OpenMeteo is validated before entering the pipeline:
- Temperature: must be between -5°C and 40°C (annual mean)
- Precipitation: must be between 0 and 4,000mm/year
- Solar radiation: must be between 0 and 10 kWh/m²/day
- Invalid records are discarded and logged automatically

### Layer 2 — Output Validation
Before returning results to the user, the system validates:
- Risk score must be greater than zero
- Executive summary must be substantive (>100 characters)
- At least one recommendation must be generated
- Minimum 5 years of NASA historical data required
- Failed validations automatically reduce confidence score and trigger Human-in-the-Loop (HITL) flag

### Layer 3 — User Notification
When data quality issues are detected:
- A "Data Quality Notice" card appears in the dashboard
- Lists specific issues found
- Confidence score is reduced proportionally
- Human expert review is strongly recommended

### Known Limitations
- NASA POWER data available from 1981 to 2025
- OpenMeteo IPCC projections available from 2027 to 2050
- Climate projections use an ensemble of 5 IPCC models (CMCC_CM2_VHR4, MRI_AGCM3_2_S, EC_Earth3P_HR, MPI_ESM1_2_XR, NICAM16_8S) to improve reliability. **Risk scores are calculated exclusively from observed NASA POWER and ERA5 data.** Projections are used only for visualization of future climate trajectories.
- Spatial resolution: ~0.5° × 0.5° (~55km at equator)
- Some remote locations may have sparse satellite coverage
- Mountain regions above 2,000m altitude may show reduced data quality due to topographic effects

### Sanity Check Thresholds
| Parameter | Valid Range | Action if Outside |
|-----------|------------|-------------------|
| Temperature mean | -5°C to 40°C | Discard record |
| Annual precipitation | 0 to 4,000mm | Discard record |
| Temp trend | -1.5 to +1.5°C/decade | Flag warning |
| Precip trend | -40% to +40%/decade | Flag warning |
| Risk score | 1 to 100 | Trigger HITL |

---

## Limitations

### Projection Methodology
- **Linear extrapolation:** Future trends are calculated using linear regression on historical data
- **Not physics-based:** We use IPCC model outputs but don't run climate simulations ourselves
- **Three scenarios available:** SSP1-2.6, SSP2-4.5, SSP5-8.5 — results vary significantly between scenarios
- **No extreme events:** Projections show gradual trends, not sudden shocks (hurricanes, wildfires)
- **Quality Judge skipped for projections:** Confidence defaults to 65 and HITL is always required when end_year > 2025

### Data Quality
- **NASA POWER coverage:** Some remote regions have sparse satellite coverage
- **Missing values:** Handled via -999.0 fill value detection and exclusion
- **Spatial resolution:** 0.5° × 0.5° grid (~55km at equator) — not building-level precision
- **Temporal gaps:** Occasional missing days in NASA data (excluded from annual aggregates)
- **Evapotranspiration:** NASA POWER parameter EVPTRNS (evapotranspiration) is equivalent to FAO-56 ET0 reference standard
- Data quality validation is automatic but not infallible. Always validate findings with qualified ESG consultants before regulatory filings — especially for high-altitude regions, small islands, and areas with sparse satellite coverage.

### System Limitations
- **No user authentication:** Current version uses session-based storage only (LGPD compliant)
- **No real-time updates:** Climate data refreshed when NASA/OpenMeteo publish new datasets
- **Batch cap:** CSV batch analysis limited to **5 regions** per submission; larger portfolios require multiple uploads
- **Comparison mode:** NASA-only; does not include ERA5 or IPCC projections; no full ESG compliance report generated
- **Single-instance batch jobs:** Batch job state is in-memory only; Redis would be required for multi-instance deployments

### Rate Limits
| Endpoint | Limit |
|----------|-------|
| `POST /api/analyze` | 10 per hour |
| `POST /api/analyze/compare` | 5 per hour |
| `POST /api/analyze/batch` | 3 per hour |
| `GET/POST /api/analyses/{id}/export/pdf` | 5 per minute |
| `GET/POST /api/analyses/{id}/export/excel` | 5 per minute |
| `GET /api/analyses` | 30 per minute |
| `GET /health` | 60 per minute |

### Compliance Disclaimer
Agentic ESG provides **decision support**, not legal advice. Organizations should:
- Validate findings with qualified ESG consultants
- Conduct site-specific assessments for critical infrastructure
- Review outputs with legal counsel before regulatory filings
- Use as one input in a broader due diligence process

---

## Setup and Installation

### Prerequisites
- Python 3.10+ (3.11+ recommended)
- MongoDB instance (local or Railway)
- Anthropic API key

### Installation

```bash
# Clone repository
git clone https://github.com/BeatrizCoder/agentic-esg.git
cd agentic-esg

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install development dependencies (for testing)
pip install -r requirements-dev.txt

# Configure environment
cp .env.example .env
# Edit .env with your API keys:
#   ANTHROPIC_API_KEY=your_key_here
#   MONGO_URL=your_mongodb_connection_string
#   ALLOWED_ORIGINS=http://localhost:8001,https://yourdomain.com
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src/aesg --cov-report=html

# Run specific test file
pytest tests/test_nasa_adapter.py -v
```

### Running Locally

```bash
# Start the server (frontend is served by FastAPI)
source venv/bin/activate
uvicorn src.aesg.backend:app --reload --port 8001

# Access at http://localhost:8001
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key from console.anthropic.com |
| `MONGO_URL` | ✅ | MongoDB connection string |
| `PORT` | No | Server port (default: 8001) |
| `ALLOWED_ORIGINS` | No | CORS origins (comma-separated, no spaces) |
| `ENVIRONMENT` | No | `development` / `staging` / `production` |

---

## Project Structure

```
agentic-esg/
├── src/aesg/
│   ├── backend.py              # FastAPI app entry point
│   ├── agents/
│   │   ├── definitions.py      # 4 CrewAI agent definitions (3 Sonnet + 1 Haiku)
│   │   ├── tasks.py            # CrewAI task factories
│   │   └── crews.py            # Crew orchestration + token tracking
│   ├── data/
│   │   ├── nasa_adapter.py     # NASA POWER API client
│   │   └── openmeteo_adapter.py # OpenMeteo ERA5 + IPCC API client
│   ├── pipeline/
│   │   ├── orchestrator.py     # 6-step sequential pipeline + comparison pipeline
│   │   └── climate_engine.py   # Deterministic risk engine (no LLM)
│   ├── api/
│   │   ├── routes.py           # FastAPI endpoints + batch job runner
│   │   └── models.py           # Pydantic request/response models
│   ├── db/
│   │   └── mongo.py            # MongoDB session storage (Motor async)
│   ├── exports/
│   │   ├── pdf_report.py       # PDF generation (reportlab)
│   │   └── excel_report.py     # Excel generation (openpyxl)
│   ├── sectors/
│   │   ├── general.yaml        # Default risk thresholds
│   │   ├── agriculture_food.yaml
│   │   ├── energy_utilities.yaml
│   │   ├── finance_banking.yaml
│   │   ├── infrastructure.yaml
│   │   ├── manufacturing.yaml
│   │   ├── real_estate.yaml
│   │   └── retail_logistics.yaml
│   └── core/
│       └── config.py           # Environment variables + rate limiter
├── prompts/
│   ├── climate_analyst.md      # Step 2b system prompt
│   ├── esg_strategist.md       # Step 3 system prompt
│   └── report_writer.md        # Step 4 system prompt
├── index.html                  # Frontend SPA
├── Dockerfile                  # Railway deployment
├── railway.toml                # Railway config
├── requirements.txt
└── README.md
```

---

## Deployment

### Railway (Recommended)

```bash
# Install Railway CLI
npm install -g @railway/cli

# Login and deploy
railway login
railway up

# Set environment variables in Railway dashboard
```

### Docker

```bash
# Build image
docker build -t agentic-esg .

# Run container
docker run -p 8001:8001 \
  -e ANTHROPIC_API_KEY=your_key \
  -e MONGO_URL=your_mongo_url \
  agentic-esg
```

---

## Quality Assurance

### Automated Testing
- **Unit tests** for NASA adapter and data processing
- **Integration tests** for API endpoints
- **Mock-based testing** for external API calls
- **GitHub Actions CI/CD** for automated testing on push

### Code Quality
- **Type hints** throughout codebase (Python 3.10+)
- **Pydantic validation** for all API inputs
- **Retry logic** for external API calls (tenacity)
- **Comprehensive error handling** with user-friendly messages
- **Configurable CORS** for production security

### Security Features
- Environment-based CORS configuration
- Rate limiting per IP address (slowapi)
- Input validation with Pydantic validators
- Session-based storage with TTL
- No hardcoded credentials

---

## License

Apache License 2.0

Copyright 2026 Beatriz Costa Leal

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.

---

## Roadmap

**What's Already Implemented:**
- ✅ Three IPCC scenarios (SSP1-2.6, SSP2-4.5, SSP5-8.5)
- ✅ Multi-language support (EN, PT, ES, FR, DE)
- ✅ Evapotranspiration and soil moisture analysis
- ✅ Three-source climate timeline (NASA + ERA5 + IPCC)
- ✅ Human-in-the-Loop (HITL) validation flag
- ✅ AI Transparency layer (EU AI Act Art. 13)
- ✅ ESG Glossary (5 languages)
- ✅ Terms of Use and Privacy Policy (scroll-to-accept)
- ✅ PDF and Excel export (individual + batch)
- ✅ Session history with 30-day TTL (LGPD compliant)
- ✅ Historical comparison mode — compare climate risk between two time periods for the same location
- ✅ 8 sector-specific risk profiles (agriculture, real estate, energy, finance, infrastructure, manufacturing, retail/logistics, general)
- ✅ Three-layer data quality validation system — input filtering, output validation, and user notification for unreliable results
- ✅ Batch CSV analysis (up to 5 regions, with optional comparison columns)

**Near-term:**
- [ ] API key authentication for enterprise use
- [ ] Batch analysis expanded to 20 regions
- [ ] Vector database for regulation knowledge base (ChromaDB)

**Medium-term:**
- [ ] Integration with GIS platforms (ArcGIS, QGIS)
- [ ] Physics-based climate models (WRF, RegCM)

**Long-term:**
- [ ] Extreme event probability modeling
- [ ] Portfolio-level risk aggregation
- [ ] Real-time monitoring and alerts

---

## Acknowledgments

**Data Sources:**
- NASA POWER Project (Prediction Of Worldwide Energy Resources)
- Open-Meteo ERA5 Climate Reanalysis
- Open-Meteo IPCC Climate API (AR6 Models)

**Frameworks:**
- CrewAI by João Moura
- FastAPI by Sebastián Ramírez
- Anthropic Claude AI

**Development:**
- Built with Claude Code (Anthropic) — architecture, features, and business logic
- IBM Bob (watsonx Code Assistant) — AI assistant used for deployment configuration, documentation, and code review. Code architecture and business logic designed by Beatriz Costa Leal.
- Inspired by the "Become An Agentic Architect" course

---

*Built by Beatriz Costa — June 2026*  
*Open source for educational and research purposes*  
*Contact: biagenai24@outlook.com*
