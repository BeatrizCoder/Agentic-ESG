# Climate Sentinel — Climate Risk Intelligence for ESG & Compliance

[![Tests](https://github.com/BeatrizCoder/climate-sentinel/actions/workflows/tests.yml/badge.svg)](https://github.com/BeatrizCoder/climate-sentinel/actions/workflows/tests.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-Apache%202.0-green.svg)](LICENSE)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

> Physical climate risk assessment powered by NASA satellite data, IPCC projections, and Claude AI agents.

🌐 **Live Demo:** [Coming Soon]
📦 **GitHub:** https://github.com/BeatrizCoder/climate-sentinel

---

## Overview

Organizations face mounting regulatory pressure to assess and disclose physical climate risks under CSRD, ISSB S2, and EU Taxonomy. Traditional climate risk assessments cost $5,000–$50,000 and take weeks. Climate Sentinel delivers executive-ready climate risk intelligence in under 30 seconds for ~$0.03 per location — powered by real NASA satellite data and IPCC projections to 2050.

> **Maps physical climate risk to CSRD ESRS E1, ISSB S2, and EU Taxonomy — translating satellite data into compliance-ready business intelligence.**

**Built for:** ESG analysts, sustainability officers, investment managers, and compliance teams who need fast, data-driven climate risk intelligence.

---

## The Problem

Organizations face mounting pressure to assess and disclose physical climate risks:

- **CSRD (Corporate Sustainability Reporting Directive)** — EU companies must report climate risks under ESRS E1 by 2024-2025
- **ISSB S2 (Climate-related Disclosures)** — Global standard requiring scenario analysis and physical risk assessment
- **EU Taxonomy** — Investment screening requires climate risk evaluation for sustainable finance classification
- **Traditional assessments** — Manual climate risk analysis costs $5,000-$50,000 and takes weeks

Climate Sentinel delivers executive-ready climate risk assessment in under 30 seconds for ~$0.03 per location.

---

## How It Works

### The Pipeline (Sequential Agent Architecture)

```
Location Input (lat/lon)
        ↓
┌───────────────────────────────────────────────────────────┐
│ Agent 1: Data Collector (Python adapter — no LLM)        │
│   • NASA POWER API: 10 years real satellite data         │
│   • OpenMeteo IPCC: Climate projections 2026-2050        │
│   • Parameters: temperature, precipitation, solar         │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Agent 2: Climate Analyst (Claude Haiku 4.5)              │
│   • Detects trends: warming rate, precipitation shifts   │
│   • Identifies anomalies: extreme years, heat stress     │
│   • Calculates risks: drought, flood, heat stress        │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Agent 3: ESG Strategist (Claude Sonnet 4.6)              │
│   • Maps risks to CSRD ESRS E1 articles                  │
│   • Evaluates ISSB S2 scenario requirements              │
│   • Assesses EU Taxonomy climate criteria                │
│   • Determines compliance urgency                         │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Agent 4: Report Writer (Claude Sonnet 4.6)               │
│   • Generates executive summary                           │
│   • Calculates physical risk score (0-100)               │
│   • Assigns investment status badge                       │
│   • Provides framework-specific recommendations          │
│   • Defines ecosystem offset targets                      │
└───────────────────────────────────────────────────────────┘
        ↓
┌───────────────────────────────────────────────────────────┐
│ Agent 5: Validation Layer (Claude Sonnet 4.6)            │
│   • Validates output coherence                            │
│   • Flags inconsistencies across agent outputs            │
│   • Assigns confidence score (0-100)                      │
└───────────────────────────────────────────────────────────┘
        ↓
    Final Report
```

### Data Sources

**NASA POWER API (2000-2025)**
- Real satellite observations from NASA's POWER project
- Daily resolution: temperature (T2M), precipitation (PRECTOTCORR), solar irradiance (ALLSKY_SFC_SW_DWN)
- Global coverage at 0.5° × 0.5° resolution
- Aggregated to annual statistics for trend analysis

**OpenMeteo IPCC Climate API (2026-2050)**
- IPCC AR6 climate projections using EC_Earth3P_HR model
- Daily resolution: temperature, precipitation
- Extends historical data with future scenarios
- Enables long-term risk forecasting

### Agent Details

| Agent | Model | Role | Output |
|-------|-------|------|--------|
| **Data Collector** | Python + httpx | Fetches and normalizes climate data | Annual records (temp, precip, solar) |
| **Climate Analyst** | Claude Haiku 4.5 | Detects trends and anomalies | Risk levels, key findings, data quality |
| **ESG Strategist** | Claude Sonnet 4.6 | Maps risks to compliance frameworks | CSRD/ISSB/Taxonomy exposure + urgency |
| **Report Writer** | Claude Sonnet 4.6 | Generates executive report | Risk score, summary, recommendations |
| **Validation Layer** | Claude Sonnet 4.6 | Validates output coherence, flags inconsistencies | Confidence score (0-100) |

---

## Key Features

### Risk Assessment
- **Physical Climate Risk Score (0-100)** — Quantitative measure of location-specific climate exposure
- **Investment Status Badge** — Approved / Conditioned / Restricted / Suspended (based on risk thresholds)
- **Risk Level Classification** — Low / Moderate / High / Severe / Critical
- **Trend Analysis** — Temperature and precipitation changes per decade
- **Anomaly Detection** — Identifies extreme years (hottest, driest, wettest)

### ESG Compliance Mapping
- **CSRD ESRS E1** — Article-level mapping (E1-1 through E1-9) with exposure assessment
- **ISSB S2** — Scenario analysis requirements and disclosure recommendations
- **EU Taxonomy** — Climate adaptation criteria evaluation (Annex I, Appendix A)
- **Double Materiality Assessment** — Impact and financial materiality per CSRD ESRS 1
- **Compliance Urgency** — Low / Medium / High / Critical priority classification

### Climate Projections
- **Historical Baseline** — 10 years of NASA satellite observations (2014-2023)
- **Future Scenarios** — IPCC projections to 2050 (EC_Earth3P_HR model)
- **Unified Timeline** — Seamless integration of historical + projected data
- **Trend Extrapolation** — Linear warming/precipitation trends with confidence intervals

### Ecosystem Offsets
- **Science-Based Targets** — Reforestation, wetland restoration, mangrove protection
- **Quantified Requirements** — Hectares, carbon sequestration potential, biodiversity impact
- **Regional Adaptation** — Tailored to local ecosystem and climate conditions

### User Experience
- **Session History** — MongoDB-backed analysis storage with cookie consent (LGPD compliant)
- **Dark/Light Theme** — Automatic system preference detection + manual toggle
- **EN/PT Language Toggle** — Full bilingual support (English/Portuguese)
- **PDF Export** — Professional report generation with charts and tables
- **Interactive Map** — Click-to-analyze any location globally

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
- **Climate Data:** NASA POWER API v2.5 (free, no auth required)
- **Projections:** OpenMeteo IPCC Climate API (free, no auth required)
- **Database:** MongoDB via Railway (session storage)

### Frontend
- **Stack:** Vanilla HTML/CSS/JavaScript (no framework)
- **Styling:** Custom CSS with glassmorphism effects
- **Charts:** Chart.js for data visualization
- **Maps:** Leaflet.js for interactive location selection

### Deployment
- **Backend:** Railway (Docker container)
- **Database:** MongoDB on Railway
- **Frontend:** Served via FastAPI static files
- **Domain:** Custom domain via Railway

### Development Tools
- **Development Tools:** Built with Claude Code (Anthropic) for initial architecture and IBM Bob for deployment, documentation, and optimizations.
- **Version Control:** Git + GitHub
- **Environment:** WSL2 Ubuntu on Windows 11

---

## Auditability & Transparency

Climate Sentinel is designed for auditability:

- **Data provenance:** NASA endpoint URL + OpenMeteo model identifier logged per analysis
- **Timestamp:** Exact analysis datetime recorded and stored
- **Agent execution trace:** Per-agent token consumption visible in the Data Sources tab
- **Confidence score:** Validation layer scores each output 0–100, flags inconsistencies
- **Session isolation:** Anonymous 24h TTL session cookies, LGPD compliant

All provenance data visible in the **Data Sources** tab of every analysis report.

---

## Cost Per Analysis

**~$0.03 per full analysis** (5 LLM agents)

| Agent | Model | Avg Tokens | Avg Cost |
|-------|-------|-----------|---------|
| Data Collector | Python (no LLM) | 0 | $0.000 |
| Climate Analyst | Haiku 4.5 | ~800 | $0.002 |
| ESG Strategist | Sonnet 4.6 | ~1,200 | $0.009 |
| Report Writer | Sonnet 4.6 | ~1,500 | $0.012 |
| Validation Layer | Sonnet 4.6 | ~1,000 | $0.008 |
| **Total** | | **~4,500** | **~$0.031** |

*Costs based on Anthropic pricing: Haiku $0.25/$1.25 per MTok (in/out), Sonnet $3/$15 per MTok (in/out)*

---

## Live Demo

[Link to be added after deployment]

**Try these locations:**
- São Paulo, Brazil: -23.5505, -46.6333
- Miami, USA: 25.7617, -80.1918
- Mumbai, India: 19.0760, 72.8777
- Amsterdam, Netherlands: 52.3676, 4.9041

---

## Architecture

### Adapter Pattern
The Data Collector (Agent 1) is a **pure Python adapter** — no LLM involved. It:
1. Fetches raw JSON from NASA POWER and OpenMeteo APIs
2. Normalizes data structures (handles missing values, unit conversions)
3. Aggregates daily observations into annual statistics
4. Serializes records into a compact JSON format for downstream agents

This design keeps data collection **fast, deterministic, and cost-free** (no LLM tokens).

### Sequential Agent Pipeline
Agents run **sequentially** (not in parallel) because each depends on the previous agent's output:
- Agent 2 needs normalized data from Agent 1
- Agent 3 needs climate findings from Agent 2
- Agent 4 needs both climate + compliance summaries
- Agent 5 validates the entire chain

**Total pipeline time:** ~25-30 seconds (including API calls)

### Token Optimization
- **Compact summaries:** Each agent receives only the fields it needs (not full raw data)
- **JSON serialization:** Structured output parsing with fallback to regex extraction
- **Silent execution:** CrewAI console output suppressed to avoid TTY errors on servers

---

## Limitations

### Projection Methodology
- **Linear extrapolation:** Future trends are calculated using linear regression on historical data
- **Not physics-based:** We use IPCC model outputs (EC_Earth3P_HR) but don't run climate simulations ourselves
- **Single scenario:** Currently uses SSP2-4.5 (middle-of-the-road emissions scenario)
- **No extreme events:** Projections show gradual trends, not sudden shocks (hurricanes, wildfires)

### Data Quality
- **NASA POWER coverage:** Some remote regions have sparse satellite coverage
- **Missing values:** Handled via -999.0 fill value detection and exclusion
- **Spatial resolution:** 0.5° × 0.5° grid (~55km at equator) — not building-level precision
- **Temporal gaps:** Occasional missing days in NASA data (excluded from annual aggregates)

### System Limitations
- **No user authentication:** Current version uses session-based storage only (LGPD compliant)
- **No real-time updates:** Climate data refreshed when NASA/OpenMeteo publish new datasets
- **Single location analysis:** Batch processing not yet implemented
- **English/Portuguese only:** Other languages require prompt translation

### Compliance Disclaimer
Climate Sentinel provides **decision support**, not legal advice. Organizations should:
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
git clone https://github.com/BeatrizCoder/climate-sentinel.git
cd climate-sentinel

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
#   ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

### Running Tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage report
pytest tests/ --cov=src/cs --cov-report=html

# Run specific test file
pytest tests/test_nasa_adapter.py -v
```

### Running Locally

```bash
# Terminal 1: Backend
source venv/bin/activate
uvicorn src.cs.backend:app --reload --port 8001

# Terminal 2: Frontend (if serving separately)
python -m http.server 8080

# Access at http://localhost:8001
```

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `ANTHROPIC_API_KEY` | ✅ | Claude API key from console.anthropic.com |
| `MONGO_URL` | ✅ | MongoDB connection string |
| `PORT` | No | Server port (default: 8001) |
| `ALLOWED_ORIGINS` | No | CORS origins (default: "*") |

---

## Project Structure

```
climate-sentinel/
├── src/cs/
│   ├── backend.py              # FastAPI app entry point
│   ├── agents/
│   │   ├── definitions.py      # 5 CrewAI agent definitions
│   │   ├── tasks.py            # CrewAI task factories
│   │   └── crews.py            # Crew orchestration + token tracking
│   ├── data/
│   │   ├── nasa_adapter.py     # NASA POWER API client
│   │   └── openmeteo_adapter.py # OpenMeteo IPCC API client
│   ├── pipeline/
│   │   └── orchestrator.py     # Sequential agent pipeline
│   ├── api/
│   │   ├── routes.py           # FastAPI endpoints
│   │   └── models.py           # Pydantic request/response models
│   ├── db/
│   │   └── mongo.py            # MongoDB session storage
│   ├── exports/
│   │   └── pdf_report.py       # PDF generation
│   └── core/
│       └── config.py           # Environment variables
├── prompts/
│   ├── climate_analyst.md      # Agent 2 system prompt
│   ├── esg_strategist.md       # Agent 3 system prompt
│   └── report_writer.md        # Agent 4 system prompt
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
docker build -t climate-sentinel .

# Run container
docker run -p 8001:8001 \
  -e ANTHROPIC_API_KEY=your_key \
  -e MONGO_URL=your_mongo_url \
  climate-sentinel
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
- Rate limiting per IP address
- Input validation with Pydantic validators
- Session-based storage with TTL
- No hardcoded credentials

---

## License

Apache License 2.0

Copyright 2026 Beatriz Costa

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

**Near-term:**
- [ ] Batch location analysis (CSV upload)
- [ ] Additional IPCC scenarios (SSP1-2.6, SSP5-8.5)
- [ ] Historical comparison mode (1980-2000 vs 2000-2020)
- [ ] API rate limiting and authentication

**Medium-term:**
- [ ] Vector database for regulation knowledge base (ChromaDB)
- [ ] Multi-language support (ES, FR, DE)
- [ ] Custom sector risk profiles (agriculture, real estate, energy)
- [ ] Integration with GIS platforms (ArcGIS, QGIS)

**Long-term:**
- [ ] Physics-based climate models (WRF, RegCM)
- [ ] Extreme event probability modeling
- [ ] Portfolio-level risk aggregation
- [ ] Real-time monitoring and alerts

---

## Acknowledgments

**Data Sources:**
- NASA POWER Project (Prediction Of Worldwide Energy Resources)
- Open-Meteo IPCC Climate API
- IPCC AR6 Climate Models (EC_Earth3P_HR)

**Frameworks:**
- CrewAI by João Moura
- FastAPI by Sebastián Ramírez
- Anthropic Claude AI

**Development:**
- Built with Claude Code (Anthropic) and IBM Bob
- Inspired by the "Become An Agentic Architect" course

---

*Built by Beatriz Costa — June 2026*  
*Open source for educational and research purposes*  
*Contact: beatrizcostaleal1996@gmail.com*
