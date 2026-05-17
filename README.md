# 🤖 Agentic Support Platform

> Multi-agent AI customer support platform built with FastAPI, CrewAI Flow, Claude Haiku 4.5, and vanilla JS.
> Capstone project — "Become An Agentic Architect" course by Carmelo Iaria.

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Agent Pipeline](#agent-pipeline)
- [LLM vs Deterministic — Decision Matrix](#llm-vs-deterministic)
- [External API Integrations](#external-api-integrations)
- [Knowledge Base (RAG)](#knowledge-base-rag)
- [Routing Engine](#routing-engine)
- [HITL — Human in the Loop](#hitl)
- [Observability & Metrics](#observability--metrics)
- [Frontend](#frontend)
- [Setup & Installation](#setup--installation)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Overview

The Agentic Support Platform is a production-grade multi-agent customer support system that combines LLM intelligence with deterministic business rules to handle customer inquiries automatically — and escalate to humans when needed.

**Key capabilities:**
- 5 specialized AI agents running in a CrewAI Flow pipeline
- Intelligent routing by category, sentiment, and available information
- Real-time external API integration (address validation + weather)
- SQLite-backed refund lookup system
- Human-in-the-loop (HITL) review with approve/reject/await
- Full observability with token tracking and cost per agent
- Dual-view: Customer Portal + Operator Dashboard

---

## Architecture

```
Customer Inquiry
      │
      ▼
┌─────────────────────────────────────────────┐
│              FastAPI Backend                │
│                                             │
│  ┌──────────┐    ┌──────────────────────┐  │
│  │ CrewAI   │    │   Routing Engine     │  │
│  │  Flow    │───▶│  (Business Rules)    │  │
│  └──────────┘    └──────────────────────┘  │
│       │                                     │
│  ┌────▼─────────────────────────────────┐  │
│  │         5 Specialized Agents         │  │
│  │                                      │  │
│  │  Classifier ──┐                      │  │
│  │               ├── (parallel)         │  │
│  │  Sentiment  ──┘                      │  │
│  │       │                              │  │
│  │  Knowledge RAG                       │  │
│  │       │                              │  │
│  │  External APIs ──▶ ViaCEP            │  │
│  │                ──▶ OpenWeatherMap    │  │
│  │                ──▶ Refund DB         │  │
│  │       │                              │  │
│  │  Response Generator (LLM)            │  │
│  │       │                              │  │
│  │  Escalation Evaluator                │  │
│  └──────────────────────────────────────┘  │
│                    │                        │
│              SQLite (tickets + refunds)     │
└─────────────────────────────────────────────┘
      │
      ▼
┌─────────────┐     ┌──────────────────────┐
│  Customer   │     │  Operator Dashboard  │
│   Portal    │     │  HITL + Analytics    │
└─────────────┘     └──────────────────────┘
```

---

## Agent Pipeline

The platform runs **5 specialized agents** in a CrewAI Flow:

| Step | Agent | Type | Description |
|------|-------|------|-------------|
| 1 | **Classification Agent** | 🤖 LLM | Categorizes inquiry + detects language |
| 2 | **Sentiment Analysis Agent** | 🤖 LLM | Detects sentiment + urgency level |
| 3 | **Routing Engine** | ⚙️ Rules | Decides routing action per category |
| 4 | **Knowledge Retrieval Agent** | ⚙️ Local | RAG search in markdown documents |
| 5 | **External Data Enrichment** | 🌐 APIs | ViaCEP + OpenWeather + Refund DB |
| 6 | **Response Generation Agent** | 🤖 LLM | Generates contextual response |
| 7 | **Summary Agent** | 🤖 LLM | Creates 2-line operator summary |
| 8 | **Escalation Evaluation Agent** | ⚙️ Rules | Decides escalate/resolve/await |

**Steps 1 and 2 run in parallel** to reduce latency.

---

## LLM vs Deterministic

Strategic decision matrix for every component:

### 🤖 Uses LLM

| Component | Why LLM | Avg Tokens | Cost/Call |
|-----------|---------|-----------|-----------|
| Classification Tool | Linguistic nuance, language detection | ~170 | ~$0.000200 |
| Sentiment Analysis | Detects irony, sarcasm, cultural context | ~145 | ~$0.000178 |
| Response Generation | Natural language, empathy, context-aware | ~620 | ~$0.001199 |
| Summary Generation | Concise operator summary | ~200 | ~$0.000250 |
| Alert Messages | Personalized logistics/weather responses | ~180 | ~$0.000220 |
| Step-by-step Guidance | Dynamic instructions with links | ~350 | ~$0.000430 |

### ⚙️ Uses Deterministic Rules (no LLM)

| Component | Why Deterministic | Latency |
|-----------|------------------|---------|
| Routing Engine | Business rules must be predictable + auditable | ~2ms |
| Escalation Evaluator | Compliance + reliability critical | ~2ms |
| Knowledge Retrieval | Local search is instant and free | ~45ms |
| CEP Validation | External API, no LLM needed | ~420ms |
| Weather Check | External API, no LLM needed | ~380ms |
| Refund DB Lookup | SQLite query, instant | ~12ms |
| Keyword Detection | Regex is faster and more reliable | <1ms |

### 💡 Cost Optimization Insight

Switching Classification + Sentiment to deterministic would save **~27.9% per session** while maintaining response quality — since the Response Agent (which uses the most tokens) would still use LLM where it matters most.

---

## External API Integrations

### 📍 ViaCEP (Address Validation)
- **URL:** `https://viacep.com.br/ws/{cep}/json/`
- **Auth:** None required
- **Usage:** Validates Brazilian postal codes, detects delivery region
- **Business rule:** CEPs from Sul/Sudeste (SP, RJ, MG, ES, PR, SC, RS) trigger logistics alert
- **Resilience:** 2 retries, 5s timeout, graceful fallback
- **Env var:** None needed

### 🌤️ OpenWeatherMap (Weather Check)
- **URL:** `https://api.openweathermap.org/data/2.5/weather`
- **Auth:** `OPENWEATHER_API_KEY`
- **Usage:** Real-time weather for customer's city
- **Business rule:** Adverse conditions in Sul cities trigger weather delay alert
- **Resilience:** 2 retries, 5s timeout, rate limit handling (429), graceful fallback
- **Env var:** `OPENWEATHER_API_KEY`

### 🗄️ Refund Database (SQLite)
- **Type:** Local SQLite table (`refunds`)
- **Auth:** Internal only
- **Usage:** Lookup refund status by order number
- **Business rules:**
  - `aprovado` / `processado` / `pendente` / `em_analise` → auto-resolve
  - `negado` → customer can accept, dispute, or request human
- **Seed data:** 10 realistic records (orders 10000–99999)

### API Business Rules

```
Customer mentions CEP in Sul/Sudeste
  → ViaCEP validates address
  → Logistics alert detected
  → LLM generates personalized response
  → Auto-resolved (no escalation needed)

Customer mentions city + delivery delay
  → OpenWeatherMap checks real-time conditions
  → If adverse: weather delay alert
  → LLM generates response with real temp/conditions
  → Auto-resolved

Customer asks about refund with order number
  → Refund DB lookup
  → If found: LLM generates status-specific response
  → If denied: customer gets 3 options (accept/dispute/human)
  → Auto-resolved or escalated based on status
```

---

## Knowledge Base (RAG)

Token-controlled retrieval from local markdown documents.

**Documents:**
```
knowledge/
  order_issues.md       ← tracking, wrong items, damaged
  billing.md            ← refunds, charges, invoices
  account_access.md     ← password reset, locked accounts, 2FA
  technical_issues.md   ← site errors, payment failures
  general_support.md    ← return policy, cancellation, contact
  escalation_policy.md  ← when to escalate, keywords (PT + EN)
```

**Token control:**
```python
MAX_KNOWLEDGE_SNIPPETS = 3    # max snippets per query
MAX_SNIPPET_CHARS = 800       # max chars per snippet
# Result: max ~600 tokens of context sent to LLM
# vs ~5,000+ tokens if full documents were sent
```

**Retrieval:**
1. Matches document by category
2. Scores sections by keyword relevance
3. Returns top N snippets only
4. Never sends full documents to LLM

---

## Routing Engine

Intelligent routing decision matrix:

| Category | Condition | Action |
|----------|-----------|--------|
| Any | Explicit escalation keyword | 🚨 Escalate immediately |
| Any | CEP in Sul/Sudeste | ✅ Auto-resolve (logistics alert) |
| Any | City + adverse weather | ✅ Auto-resolve (weather delay) |
| Any | Refund + order number found | ✅ Auto-resolve (DB lookup) |
| Any | Refund denied | 🚨 Escalate (options shown) |
| Billing | Always | 🚨 Escalate |
| Order Issues | With order number | 🚨 Escalate (has info) |
| Order Issues | Without order number | ⏳ Awaiting (request info) |
| Account Access | Security issue (hacked) | 🚨 Escalate |
| Account Access | Normal (forgot password) | 📋 Step-by-step |
| Technical Issue | With screenshot/details | 📋 Step-by-step |
| Technical Issue | Without details | ⏳ Awaiting (request info) |
| General Support | Any | ✅ Auto-resolve |

**Priority order in evaluation:**
```
1. Logistics alert    → always auto-resolve
2. Weather delay      → always auto-resolve
3. Refund found       → auto-resolve by status
4. Refund denied      → escalate with options
5. Routing decision   → apply matrix above
```

---

## HITL

Human-in-the-Loop review in the Operator Dashboard:

```
Escalated ticket → Operator reviews →

  [✅ Approve & Resolve]  → closes ticket
  [⏳ Awaiting Customer]  → marks as waiting
  [❌ Reject]             → returns for revision
```

**Pre-escalation modal:** Collects structured info before escalating:
- Order number, purchase date, amount, reason

**Awaiting form:** Dynamic fields based on missing info:
- Order number, email, screenshot (with drag & drop)

---

## Observability & Metrics

### Per-ticket (Observability tab):
- Token usage per agent (input + output + cost)
- Wall time per execution
- Execution mode (LLM vs deterministic)
- Knowledge snippets used
- External API calls and results

### Aggregated (Analytics tab):

**Customer Metrics:**
- CSAT Score (from feedback buttons)
- Not Helpful top reasons (from questionnaire)
- Tickets by category, sentiment, urgency
- Ticket timeline (last 7 days)

**System Metrics (Agent Health Dashboard):**

| Row | Metrics |
|-----|---------|
| Quality | Classification Accuracy, Avg Response Time, Model Confidence |
| Operational | Cost per Ticket, Fallback Rate, Pipeline Depth |
| Pipeline | KB Coverage, Fallback Rate, Throughput |
| External APIs | ViaCEP Latency, OpenWeather Latency, Refund DB Latency, API Resilience |

**Agent Performance Table:**
- Calls, avg latency, avg tokens, cost/call per agent
- Cost optimization recommendations
- Slowest/fastest agent highlights

---

## Frontend

Dual-view single-page application (vanilla JS, no framework):

### Customer Portal
- Light violet/lavender theme
- Intake form (name, email, phone)
- Quick Demo dropdown (25+ pre-filled scenarios)
- Dynamic response cards:
  - Auto-resolve (with 👍 👎 feedback)
  - Step-by-step (numbered steps + clickable links)
  - Awaiting (dynamic fields for missing info)
  - Escalation (with reference ID)
  - Refund denied (accept / dispute / talk to human)
- Not Helpful questionnaire (5 reasons + optional text)

### Operator Dashboard
- Dark glassmorphism theme
- Dataset toggle: Live Demo ↔ Historical Data
- Ticket queue with filters (status, category, API tags)
- Ticket detail tabs:
  - **Response**: AI response + HITL buttons + feedback + AI summary
  - **Agent Timeline**: colored dots per agent, collab badges
  - **Knowledge**: expandable accordion with snippets sent to LLM
  - **Observability**: token table per agent + cost breakdown
- Analytics tab (full metrics)
- Demo Controls (clear tickets, manage backups)

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js (not required — vanilla JS)
- Git

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/agentic-support-platform.git
cd agentic-support-platform

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your API keys
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | ✅ Yes | — | Claude AI API key |
| `OPENWEATHER_API_KEY` | ✅ Yes | — | OpenWeatherMap API key (free tier) |
| `INTERNAL_API_KEY` | ✅ Yes | `dev-key-change-in-production` | Operator dashboard authentication |
| `ALLOWED_ORIGINS` | No | `localhost` | CORS allowed origins |
| `MAX_KNOWLEDGE_SNIPPETS` | No | `3` | Max RAG snippets per query |
| `MAX_SNIPPET_CHARS` | No | `800` | Max characters per snippet |
| `USE_LLM` | No | `True` | Enable/disable LLM calls |
| `CREWAI_VERBOSE` | No | `false` | Verbose agent logs |
| `CREWAI_TRACING_ENABLED` | No | `true` | Enable CrewAI tracing |

---

## Running the Project

### Start everything:

```bash
# Option 1: Use the start script
chmod +x start_demo.sh
./start_demo.sh

# Option 2: Manual start
# Terminal 1 — Backend
source .venv/bin/activate
uvicorn aamad.backend:app --reload --port 8000

# Terminal 2 — Frontend
python3 -m http.server 5500
```

### Access:
- **Customer Portal:** http://localhost:5500/index.html
- **Operator Dashboard:** same URL → click "Operator View"
- **API Docs:** http://127.0.0.1:8000/docs
- **Health Check:** http://127.0.0.1:8000/health

---

## Testing

### Run external API tests:
```bash
python tests/test_external_tools.py
```

**Test coverage:**
```
✅ CEP valid (Av. Paulista, São Paulo)
✅ CEP invalid (error handled cleanly)
✅ CEP timeout (fallback returned)
✅ Weather check (São Paulo)
✅ Weather city not found (fallback)
```

### Manual test scenarios (Quick Demo dropdown):

| Scenario | Expected |
|----------|----------|
| Política de devolução | Auto-resolve, PT response |
| Return policy | Auto-resolve, EN response |
| Esqueci minha senha | Step-by-step with links |
| CEP 01310-100 (SP) | Logistics alert, auto-resolve |
| Curitiba + atraso | Weather data, auto-resolve |
| Reembolso pedido 11111 | DB lookup, R$150 approved |
| Reembolso pedido 33333 | Denied → 3 options |
| QUERO REEMBOLSO URGENTE | Pre-escalation modal |
| Conta hackeada | Immediate escalation |

---

## Project Structure

```
agentic-support-platform/
│
├── src/aamad/
│   ├── backend.py              # FastAPI + CrewAI SupportFlow
│   ├── routing_engine.py       # Intelligent routing by category
│   ├── observability.py        # Structured event tracking
│   ├── services.py             # KnowledgeService (RAG)
│   └── data_store.py           # SQLite via SQLAlchemy
│
├── tools/
│   ├── utils.py                # Shared: clean_inquiry, detect_language
│   ├── classification_tool.py  # LLM: category + language detection
│   ├── sentiment_tool.py       # LLM: sentiment + urgency
│   ├── knowledge_tool.py       # Local: RAG retrieval
│   ├── response_tool.py        # LLM: response generation
│   ├── escalation_tool.py      # Rules: keyword matching
│   ├── address_validation_tool.py  # ViaCEP API
│   ├── weather_check_tool.py       # OpenWeatherMap API
│   └── refund_lookup_tool.py       # SQLite refunds table
│
├── knowledge/
│   ├── order_issues.md
│   ├── billing.md
│   ├── account_access.md
│   ├── technical_issues.md
│   ├── general_support.md
│   └── escalation_policy.md
│
├── tests/
│   └── test_external_tools.py  # 5/5 passing
│
├── index.html                  # Complete frontend (vanilla JS)
├── start_demo.sh               # Demo startup script
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python) |
| AI Orchestration | CrewAI Flow |
| LLM | Claude Haiku 4.5 (Anthropic) |
| Database | SQLite via SQLAlchemy |
| External APIs | ViaCEP, OpenWeatherMap |
| Frontend | Vanilla JS, HTML, CSS |
| Observability | Custom ObservabilityService |

---

## Next Steps (Roadmap)

```
🔮 Near term:
  - Vector DB for advanced RAG (ChromaDB/Pinecone)
  - Streaming responses (SSE/WebSocket)
  - Authentication (JWT)
  - Deploy to cloud (Railway/Render)

🧪 LLM quality:
  - Hallucination detection (DeepEval/Ragas)
  - Faithfulness scoring
  - Answer relevance metrics
  - A/B testing prompts

📊 Analytics:
  - NPS tracking
  - Resolution time by category
  - Agent efficiency trends
  - Cost forecasting
```

---
