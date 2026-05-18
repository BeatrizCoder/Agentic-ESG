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
- [Knowledge Base RAG](#knowledge-base-rag)
- [Routing Engine](#routing-engine)
- [HITL](#hitl)
- [Observability and Metrics](#observability-and-metrics)
- [LLM Quality Evaluation](#llm-quality-evaluation)
- [Frontend](#frontend)
- [Setup and Installation](#setup-and-installation)
- [Environment Variables](#environment-variables)
- [Running the Project](#running-the-project)
- [Testing](#testing)
- [Project Structure](#project-structure)

---

## Overview

The Agentic Support Platform is a production-grade multi-agent customer support system that combines LLM intelligence with deterministic business rules to handle customer inquiries automatically and escalate to humans when needed.

**Key capabilities:**
- 5+ specialized AI agents in a CrewAI Flow pipeline
- Intelligent routing by category, sentiment, and available information
- Real-time external API integration (address validation + weather)
- SQLite-backed refund lookup system
- Human-in-the-loop (HITL) review with approve/reject/await
- Full observability with token tracking and cost per agent
- Built-in LLM quality evaluation (LLM-as-a-judge)
- Dual-view: Customer Portal + Operator Dashboard

---

## Architecture

```
Customer Inquiry
      |
      v
+---------------------------------------------+
|              FastAPI Backend                |
|                                             |
|  +----------+    +----------------------+  |
|  | CrewAI   |    |   Routing Engine     |  |
|  |  Flow    |--->|  (Business Rules)    |  |
|  +----------+    +----------------------+  |
|       |                                     |
|  +----v-------------------------------------+  |
|  |         Agent Pipeline               |  |
|  |                                      |  |
|  |  Classifier --+                      |  |
|  |               +-- (parallel)         |  |
|  |  Sentiment  --+                      |  |
|  |       |                              |  |
|  |  Knowledge RAG (local)               |  |
|  |       |                              |  |
|  |  External Data Enrichment            |  |
|  |    +--> ViaCEP API                   |  |
|  |    +--> OpenWeatherMap API           |  |
|  |    +--> Refund SQLite DB             |  |
|  |       |                              |  |
|  |  Response Generator (LLM)            |  |
|  |  + Alert Messages (LLM)              |  |
|  |       |                              |  |
|  |  Summary Agent (LLM)                 |  |
|  |       |                              |  |
|  |  Escalation Evaluator (Rules)        |  |
|  +--------------------------------------+  |
|                    |                        |
|           SQLite (tickets + refunds)        |
+---------------------------------------------+
      |
      v
+-------------+     +----------------------+
|  Customer   |     |  Operator Dashboard  |
|   Portal    |     |  HITL + Analytics    |
+-------------+     +----------------------+
```

---

## Agent Pipeline

| Step | Agent | Type | Description |
|------|-------|------|-------------|
| 1 | Classification Agent | LLM | Categorizes inquiry + detects language |
| 2 | Sentiment Analysis Agent | LLM | Detects sentiment + urgency (parallel with step 1) |
| 3 | Routing Engine | Rules | Decides routing action per category |
| 4 | Knowledge Retrieval Agent | Local | RAG search in markdown documents |
| 5 | External Data Enrichment | APIs | ViaCEP + OpenWeather + Refund DB |
| 6 | Response Generation Agent | LLM | Generates contextual + personalized response |
| 7 | Summary Agent | LLM | Creates 2-line operator summary |
| 8 | Escalation Evaluation Agent | Rules | Decides escalate/resolve/await |

Steps 1 and 2 run in parallel — saves ~750ms per request.

---

## LLM vs Deterministic

### Uses LLM — where intelligence adds value

| Component | Reason for LLM | Avg Tokens | Avg Cost/Call |
|-----------|---------------|-----------|--------------|
| Classification | Linguistic nuance + language detection (PT/EN/ES/FR) | ~170 | ~$0.000200 |
| Sentiment Analysis | Detects irony, sarcasm, cultural context | ~145 | ~$0.000178 |
| Response Generation | Empathy, context-awareness, personalization | ~620 | ~$0.001199 |
| Summary Generation | Concise 2-line operator summary | ~200 | ~$0.000250 |
| Logistics Alert Message | Personalized with real CEP + city data | ~180 | ~$0.000220 |
| Weather Alert Message | Uses real temperature + conditions from API | ~180 | ~$0.000220 |
| Refund Status Message | Empathetic, adapted to customer sentiment | ~200 | ~$0.000245 |
| Step-by-step Guidance | Dynamic instructions with links from knowledge base | ~350 | ~$0.000430 |
| Quality Evaluation | LLM-as-a-judge for faithfulness + relevance | ~300 | ~$0.000370 |

> Important: External APIs (ViaCEP, OpenWeatherMap) are called deterministically.
> But the response messages based on their data are generated by LLM for personalization.

### Uses Deterministic Rules — where reliability matters more

| Component | Reason for Rules | Avg Latency |
|-----------|-----------------|-------------|
| Routing Engine | Business rules must be predictable and auditable | ~2ms |
| Escalation Evaluator | Compliance critical — cannot hallucinate | ~2ms |
| Knowledge Retrieval | Local search is instant, free, reliable | ~45ms |
| CEP Validation (API call) | REST API call — no LLM needed | ~420ms |
| Weather Check (API call) | REST API call — no LLM needed | ~380ms |
| Refund DB Lookup | SQLite query — deterministic by definition | ~12ms |
| Escalation Keyword Detection | Regex is faster and more auditable | <1ms |
| Retry/Timeout/Fallback | Must be deterministic for reliability | <1ms |

### Cost Optimization Insight

```
Current cost breakdown per ticket:
  Classification:  $0.000200  (12.5%)
  Sentiment:       $0.000178  (11.1%)
  Response:        $0.001199  (74.9%)
  Summary:         $0.000050  (3.1%)
  Total:          ~$0.001627 per ticket

Potential optimization:
  Switch Classification + Sentiment to deterministic
  -> Save ~23.6% per ticket
  -> Response Agent still uses LLM (highest value)
  -> Dashboard shows this recommendation automatically
```

---

## External API Integrations

### ViaCEP (Address Validation)

```
Purpose:  Validates Brazilian postal codes
URL:      https://viacep.com.br/ws/{cep}/json/
Auth:     None required
Latency:  ~420ms avg
Retries:  2 attempts, 5s timeout
Fallback: Proceeds without validation if unavailable
```

Business rule:
```
CEP from Sul/Sudeste (SP, RJ, MG, ES, PR, SC, RS)
  -> Logistics alert active (fleet maintenance)
  -> LLM generates personalized response with city/address
  -> Auto-resolved

CEP from other regions
  -> No alert -> normal routing flow
```

### OpenWeatherMap (Weather Check)

```
Purpose:  Real-time weather for customer city
URL:      https://api.openweathermap.org/data/2.5/weather
Auth:     OPENWEATHER_API_KEY (free: 1000 calls/day)
Latency:  ~380ms avg
Retries:  2 attempts, 429 rate limit handling
Fallback: Proceeds without weather data if unavailable
```

Business rule:
```
City in Sul + adverse_conditions = true
  -> Weather delay alert
  -> LLM generates response with real temp + conditions
  -> Auto-resolved

Clear weather
  -> No alert -> normal routing flow
```

### Refund Database (SQLite)

```
Purpose:  Lookup refund status by order number
Type:     Local SQLite table
Latency:  ~12ms avg
Seed:     10 realistic records (orders 11111-99999)
```

Business rules:
```
aprovado / processado / pendente / em_analise
  -> LLM generates empathetic status message
  -> Auto-resolved with feedback buttons

negado
  -> Shows 3 options: accept / dispute / talk to human

Not found
  -> Investigation form (required fields)
  -> Escalates with collected details
```

---

## Knowledge Base RAG

Token-controlled retrieval from local markdown documents.

Documents:
```
knowledge/
  order_issues.md       <- tracking, wrong items, damaged
  billing.md            <- refunds, charges, invoices
  account_access.md     <- password reset, locked accounts, 2FA
  technical_issues.md   <- site errors, payment failures
  general_support.md    <- return policy, cancellation, contact
  escalation_policy.md  <- when to escalate, PT + EN keywords
```

Token control:
```python
MAX_KNOWLEDGE_SNIPPETS = 3    # max snippets per query
MAX_SNIPPET_CHARS = 800       # max chars per snippet
# Result: max ~600 tokens of context sent to LLM
# vs ~5,000+ tokens if full documents were sent
# Savings: ~88% fewer knowledge tokens
```

---

## Routing Engine

Priority-based routing decision matrix:

| Priority | Condition | Action |
|----------|-----------|--------|
| 1 | Logistics alert (Sul/Sudeste CEP) | Auto-resolve + LLM message |
| 2 | Weather delay (city + adverse) | Auto-resolve + LLM message |
| 3 | Refund found in DB | Auto-resolve + LLM message |
| 4 | Refund denied | Show options (accept/dispute/human) |
| 5 | Explicit escalation keyword | Escalate immediately |
| 6 | Billing category | Always escalate |
| 7 | Account hacked/unauthorized | Always escalate |
| 8 | Order Issues + has order number | Escalate (enough info) |
| 9 | Order Issues + no order number | Awaiting (request info) |
| 10 | Account Access (normal) | Step-by-step guidance |
| 11 | Technical Issue + has details | Step-by-step guidance |
| 12 | Technical Issue + no details | Awaiting + screenshot upload |
| 13 | General Support | Auto-resolve |

---

## HITL

Human-in-the-Loop review workflow:

```
Escalated ticket
      |
      v
Operator Dashboard
      |
      +-- Approve & Resolve  -> RESOLVED
      +-- Awaiting Customer  -> AWAITING
      +-- Reject             -> back to queue
```

Pre-escalation modal: Collects info BEFORE escalating billing/refund:
- Order number, purchase date, amount (R$), reason (dropdown)

Awaiting form: Dynamic fields based on exactly what is missing:
- Order number, email, screenshot (drag and drop + clipboard paste)

---

## Observability and Metrics

Per-ticket (Observability tab):
```
Token Usage per Agent:
  Classification:  in=145  out=21   cost=$0.000200
  Sentiment:       in=256  out=28   cost=$0.000317
  Knowledge:       -       -        - (local, free)
  Response:        in=716  out=362  cost=$0.002021
  Escalation:      -       -        - (rules, free)
  Total:           1,117   411      $0.002538
```

Aggregated (Analytics tab):

Customer Metrics:
- CSAT Score (from feedback buttons)
- Top Not Helpful Reasons (from questionnaire)
- Tickets by category, sentiment, urgency
- Ticket timeline (last 7 days)
- External API Business Impact

System Metrics — Agent Health Dashboard (9 cards):

| Row | Cards |
|-----|-------|
| Quality | Classification Accuracy, Avg Response Time, Model Confidence |
| Operational | Cost per Ticket, Fallback Rate, Avg Pipeline Depth |
| Pipeline | KB Coverage, Throughput, Fallback Rate |
| External APIs | ViaCEP Latency, OpenWeather Latency, Refund DB Latency, API Resilience |

---

## LLM Quality Evaluation

Built-in quality evaluation using LLM-as-a-judge pattern.
No external libraries required.

```python
evaluation_prompt = f"""
Evaluate this support response:

Customer inquiry: {inquiry}
Generated response: {response}
Category: {category}

Score 0-10:
- faithfulness: uses real data or hallucinates?
- relevance: answers what was asked?
- empathy: warm and professional?
- completeness: answer is complete?

Return JSON with scores + issues + suggestion.
"""
```

Why LLM-as-a-judge instead of DeepEval/Ragas:

| DeepEval/Ragas require | Our approach |
|------------------------|--------------|
| Pre-defined ground truth | No ground truth needed |
| External API accounts | Uses existing Anthropic key |
| Static evaluation dataset | Evaluates every response live |
| Extra pip dependencies | Zero extra dependencies |

Trade-off: LLM-as-a-judge has self-evaluation bias.
For production, combining with DeepEval benchmarks is recommended.

---

## Frontend

Dual-view single-page application (vanilla JS, no framework):

### Customer Portal (light violet theme)
- Intake form: name, email, phone, privacy checkbox
- Quick Demo dropdown: 25+ pre-filled scenarios
- Dynamic response cards:
  - Auto-resolve: response + feedback buttons
  - Step-by-step: numbered steps + clickable links
  - Awaiting: dynamic fields + screenshot upload
  - Escalation: reference ID + confirmation
  - Refund denied: accept / dispute / talk to human

### Operator Dashboard (dark glassmorphism theme)
- Dataset Toggle: Live Demo vs Historical Data (read-only)
- Ticket queue with filters: status, category, API tags
- API tags: Logistics Alert, Weather Alert, Refund Found, Refund Denied
- Ticket detail tabs:
  - Response: AI response + AI Summary + HITL buttons + feedback
  - Agent Timeline: colored dots, collab badges, deduplication
  - Knowledge: expandable accordion with snippets sent to LLM
  - Observability: token table per agent + cost breakdown
- Analytics tab (customer + system metrics)
- Demo Controls: clear tickets, manage backups

---

## Setup and Installation

Prerequisites: Python 3.11+, Git

```bash
git clone https://github.com/your-username/agentic-support-platform.git
cd agentic-support-platform

python3 -m venv .venv
source .venv/bin/activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env with your API keys
```

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| ANTHROPIC_API_KEY | Yes | - | Claude Haiku 4.5 API key |
| OPENWEATHER_API_KEY | Yes | - | OpenWeatherMap free tier |
| INTERNAL_API_KEY | Yes | dev-key-change-in-production | Operator auth |
| ALLOWED_ORIGINS | No | localhost | CORS origins |
| MAX_KNOWLEDGE_SNIPPETS | No | 3 | Max RAG snippets |
| MAX_SNIPPET_CHARS | No | 800 | Max chars per snippet |
| USE_LLM | No | True | Enable/disable LLM |
| CREWAI_VERBOSE | No | false | Verbose agent logs |
| CREWAI_TRACING_ENABLED | No | true | CrewAI tracing |

---

## Running the Project

```bash
# Option 1 - Start script
chmod +x start_demo.sh
./start_demo.sh

# Option 2 - Manual
# Terminal 1
source .venv/bin/activate
uvicorn aamad.backend:app --reload --port 8000

# Terminal 2
python3 -m http.server 5500
```

Access:
- Customer Portal: http://localhost:5500/index.html
- Operator Dashboard: same URL -> Operator View
- API Docs: http://127.0.0.1:8000/docs
- Health Check: http://127.0.0.1:8000/health

---

## Testing

```bash
# External API tests
python tests/test_external_tools.py

# Expected:
# OK CEP valid -> Av. Paulista, Sao Paulo - SP (590ms)
# OK CEP invalid -> error handled cleanly
# OK CEP timeout -> fallback returned
# OK Weather Sao Paulo -> conditions + temperature
# OK Weather city not found -> fallback handled
```

Manual test scenarios:

| Input | Expected |
|-------|----------|
| "Qual a politica de devolucao?" | Auto-resolve, PT |
| "What is the return policy?" | Auto-resolve, EN |
| "Esqueci minha senha" | Step-by-step |
| "Minha conta foi hackeada" | Escalate immediately |
| "Meu pedido nao chegou" | Awaiting (no order number) |
| "Pedido 12345 nao chegou" | Escalate (has order number) |
| "CEP 01310-100" | ViaCEP -> logistics alert |
| "Sou de Curitiba, pedido atrasou" | OpenWeather -> real conditions |
| "Reembolso pedido 11111" | DB -> approved R$150 |
| "Reembolso pedido 33333" | DB -> denied -> 3 options |
| "QUERO REEMBOLSO URGENTE" | Pre-escalation modal |

---

## Project Structure

```
agentic-support-platform/
|
+-- src/aamad/
|   +-- backend.py              # FastAPI + CrewAI SupportFlow
|   +-- routing_engine.py       # Priority routing matrix
|   +-- observability.py        # Structured event tracking
|   +-- services.py             # KnowledgeService (RAG)
|   +-- data_store.py           # SQLite via SQLAlchemy
|
+-- tools/
|   +-- utils.py                    # clean_inquiry, detect_language
|   +-- classification_tool.py      # LLM: category + language
|   +-- sentiment_tool.py           # LLM: sentiment + urgency
|   +-- knowledge_tool.py           # Local: RAG retrieval
|   +-- response_tool.py            # LLM: response + alerts
|   +-- escalation_tool.py          # Rules: keyword matching
|   +-- address_validation_tool.py  # ViaCEP API
|   +-- weather_check_tool.py       # OpenWeatherMap API
|   +-- refund_lookup_tool.py       # SQLite refunds
|   +-- quality_evaluator.py        # LLM-as-a-judge (Sonnet)
|
+-- knowledge/
|   +-- order_issues.md
|   +-- billing.md
|   +-- account_access.md
|   +-- technical_issues.md
|   +-- general_support.md
|   +-- escalation_policy.md
|
+-- tests/
|   +-- test_external_tools.py  # 5/5 passing
|
+-- index.html                  # Full frontend (vanilla JS)
+-- start_demo.sh               # Demo startup script
+-- requirements.txt
+-- .env.example
+-- .gitignore
+-- README.md
```

---

## Tech Stack

| Layer | Technology | Why |
|-------|-----------|-----|
| Backend | FastAPI | Fast, async, auto-docs |
| AI Orchestration | CrewAI Flow | Multi-agent pipeline |
| LLM | Claude Haiku 4.5 | Fast + cost-effective |
| Database | SQLite + SQLAlchemy | Zero-config, reliable |
| Address API | ViaCEP | Brazilian CEPs, free |
| Weather API | OpenWeatherMap | Real-time, free tier |
| Frontend | Vanilla JS | Zero dependencies |
| Observability | Custom service | Token + cost tracking |

---

## Roadmap

```
Near term:
  - Vector DB for semantic RAG (ChromaDB/Pinecone)
  - Streaming responses (SSE/WebSocket)
  - JWT authentication
  - Cloud deploy (Railway/Render)

LLM quality:
  - Hallucination detection benchmark
  - Faithfulness scoring with ground truth
  - A/B testing prompts
  - DeepEval/Ragas integration

Analytics:
  - NPS tracking
  - Resolution time by category
  - Cost forecasting per category
```

---
