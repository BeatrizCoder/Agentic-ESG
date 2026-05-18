from crewai import Agent, Flow
from crewai.flow.flow import start, listen, and_
from crewai.tools import BaseTool
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import APIKeyHeader
from pydantic import BaseModel, Field
import yaml
import hashlib
import random
import unicodedata
import logging
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import asyncio
import time
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

# Import new services and config
from .config import USE_LLM, ENABLE_MEMORY, ENABLE_CREWAI_KNOWLEDGE, DEFAULT_CONFIG, ENABLE_EXTERNAL_APIS, ENABLE_MOCK_INTEGRATIONS
from .services import KnowledgeService, MemoryService, PromptService, SkillService
from .observability import ObservabilityService, ObservabilityEvent
from .routing_engine import route_ticket, RoutingDecision
from .tool_registry import ToolRegistry
from .data_store import data_store, SupportTicketData, SupportTicketDB
from .integrations.ticketing_client import TicketingClient
from .integrations.crm_client import CRMClient
from .integrations.notification_client import NotificationClient

# Import tools
from tools.classification_tool import ClassificationTool
from tools.sentiment_tool import SentimentTool
from tools.knowledge_tool import KnowledgeTool
from tools.response_tool import ResponseTool
from tools.escalation_tool import EscalationTool
from tools.memory_tool import MemoryTool
from tools.prompt_tool import PromptTool
from tools.rest_api_tool import RESTApiTool
from tools.graphql_api_tool import GraphQLApiTool
from tools.weather_tool import WeatherTool
from tools.github_tool import GitHubTool
from tools.address_validation_tool import AddressValidationTool
from tools.weather_check_tool import WeatherCheckTool
from tools.refund_lookup_tool import RefundLookupTool, is_refund_inquiry, extract_order_number
from tools.quality_evaluator import quality_evaluator

# Load environment variables
load_dotenv()

# API key authentication
_API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "dev-key-change-in-production")


async def verify_api_key(api_key: str = Security(_API_KEY_HEADER)):
    if api_key != INTERNAL_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid or missing API key")
    return api_key


# Load configuration
with open("config/agents.yaml", "r") as f:
    agents_config = yaml.safe_load(f)

with open("config/tasks.yaml", "r") as f:
    tasks_config = yaml.safe_load(f)


def _is_portuguese(text: str) -> bool:
    en_words = [
        'what', 'how', 'where', 'when', 'why', 'is',
        'the', 'your', 'my', 'order', 'return', 'policy',
        'refund', 'help', 'please', 'can', 'could',
        'have', 'not', 'arrived', 'want', 'need', 'this',
    ]
    pt_words = [
        'meu', 'minha', 'não', 'nao', 'quero', 'preciso',
        'pedido', 'ajuda', 'problema', 'como', 'olá',
        'obrigado', 'produto', 'conta', 'chegou', 'estou',
        'política', 'politica', 'devolução', 'devolucao',
        'qual', 'reembolso', 'estorno', 'fatura', 'prazo',
    ]
    text_lower = text.lower()
    en_score = sum(1 for w in en_words if w in text_lower)
    pt_score = sum(1 for w in pt_words if w in text_lower)
    return pt_score > en_score


class SupportTicket(BaseModel):
    inquiry: str


class FeedbackRequest(BaseModel):
    helpful: bool
    comments: Optional[str] = None
    approval_status: Optional[str] = Field(None, description="approved/rejected/needs_revision")


class StatusResponse(BaseModel):
    reference_id: str
    status: str
    created_at: str
    updated_at: str
    escalation_required: bool
    escalation_reason: Optional[str] = None


class StepsResponse(BaseModel):
    reference_id: str
    steps: List[Dict[str, Any]]
    status: str


class TraceResponse(BaseModel):
    reference_id: str
    run_id: str
    steps: List[Dict[str, Any]]
    total_steps: int
    execution_time_ms: int
    tools_used: List[str]
    tracing_enabled: bool


class RunMetrics(BaseModel):
    run_id: str
    reference_id: str
    status: str
    started_at: float
    finished_at: Optional[float] = None
    wall_time_sec: Optional[float] = None
    token_usage: Dict[str, int] = {}
    tool_latency_ms: Dict[str, float] = {}
    step_count: int = 0
    success_rate: float = 1.0
    error: Optional[str] = None


class SupportResponse(BaseModel):
    inquiry: str
    category: str
    category_confidence: int
    sentiment: str
    sentiment_confidence: int
    urgency: str
    articles: list[str]
    response: str
    response_confidence: int
    escalation_required: bool
    escalation_reason: str
    reference_id: str
    triggered_keyword: str | None = None
    steps: list[dict[str, Any]]
    knowledge_source: str | None = None
    memory_saved: bool | None = None
    execution_mode: str | None = None
    prompt_template_used: str | None = None
    skills_used: list[str] | None = None
    tools_used: list[str] | None = None
    cache_used: bool | None = None
    run_id: str | None = None
    wall_time_sec: float | None = None
    token_usage: dict | None = None
    cost_usd: float | None = None
    routing_action: str | None = None
    routing_reason: str | None = None
    routing_missing_info: list[str] | None = None
    api_tags: list[str] | None = None
    quality_evaluation: dict | None = None


class SupportState(BaseModel):
    inquiry: str = ""
    category: str = "General Support"
    category_confidence: int = 0
    sentiment: str = "Neutral"
    sentiment_confidence: int = 0
    urgency: str = "Low"
    articles: list[str] = []
    response: str = ""
    response_confidence: int = 0
    escalation_required: bool = False
    escalation_reason: str = ""
    reference_id: str = ""
    triggered_keyword: str | None = None
    steps: list[dict[str, Any]] = []
    knowledge_source: str = "unknown"
    memory_saved: bool = False
    execution_mode: str = "deterministic"
    prompt_template_used: str | None = None
    skills_used: list[str] = []
    tools_used: list[str] = []
    cache_used: bool = False
    run_id: str = ""
    token_usage: dict = {}
    cost_usd: float = 0.0
    knowledge_context: str = ""
    knowledge_sources: list[str] = []
    estimated_context_tokens: int = 0
    routing_action: str = ""
    routing_reason: str = ""
    routing_missing_info: list[str] = []
    routing_confidence: float = 0.0
    external_context: str = ""
    logistics_alert: dict = {}
    weather_delay: dict = {}
    refund_data: dict = {}
    api_tags: list[str] = []
    auto_resolve_reason: str = ""
    quality_evaluation: dict = {}

    def log_step(self, agent_name: str, details: dict[str, Any]) -> None:
        self.steps.append({
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
            "details": details
        })


class SupportCrew:
    def __init__(self):
        self.agents = {}
        self.steps: list[dict[str, Any]] = []
        self._create_agents()

    def _create_agents(self):
        """Create agents from configuration with tools"""
        for agent_name, config in agents_config.items():
            # Add tools based on agent role
            tools = []
            if agent_name == "classifier_agent":
                tools.append(ClassificationTool())
            elif agent_name == "sentiment_agent":
                tools.append(SentimentTool())
            elif agent_name == "knowledge_agent":
                tools.append(KnowledgeTool())
            elif agent_name == "response_agent":
                tools.append(ResponseTool())
            elif agent_name == "escalation_agent":
                tools.append(EscalationTool())

            self.agents[agent_name] = Agent(
                role=config["role"],
                goal=config["goal"],
                backstory=config["backstory"],
                tools=tools,
                verbose=os.environ.get("CREWAI_VERBOSE", "false").lower() == "true"
            )

    def log_step(self, agent_name: str, details: dict[str, Any]) -> None:
        self.steps.append({"agent": agent_name, "details": details})

    def execute_tool(self, agent_key: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        agent = self.agents[agent_key]
        tool = agent.tools[0]
        result = tool._run(*args, **kwargs)
        self.log_step(agent.role, {
            "tool_used": tool.name,
            "input": args,
            "kwargs": kwargs,
            "output": result,
        })
        return result

    def ask_agent(self, from_agent: str, to_agent: str, question: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        self.log_step(from_agent, {
            "collaboration": "ask",
            "target_agent": to_agent,
            "question": question,
            "context": context,
        })
        response = f"{to_agent} acknowledged the question: {question}"
        self.log_step(to_agent, {
            "collaboration": "respond",
            "from_agent": from_agent,
            "response": response,
        })
        return response

    def delegate_task(self, from_agent: str, to_agent: str, task_description: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        self.log_step(from_agent, {
            "collaboration": "delegate",
            "target_agent": to_agent,
            "task": task_description,
            "context": context,
        })
        result = f"{to_agent} completed task: {task_description}"
        self.log_step(to_agent, {
            "collaboration": "task_completed",
            "from_agent": from_agent,
            "result": result,
        })
        return result

    def process_support_request(self, inquiry: str) -> Dict[str, Any]:
        """Process a support request using tools and agent orchestration"""
        self.steps = []

        classification_result = self.execute_tool("classifier_agent", inquiry)
        sentiment_result = self.execute_tool("sentiment_agent", inquiry)
        knowledge_result = self.execute_tool("knowledge_agent", classification_result["category"], inquiry)

        self.ask_agent(
            "Response Generation Agent",
            "Knowledge Retrieval Agent",
            f"What articles are available for category '{classification_result['category']}'?",
            {"current_category": classification_result["category"]},
        )

        response_result = self.execute_tool(
            "response_agent",
            classification_result["category"],
            sentiment_result["urgency"],
            knowledge_result["count"],
            inquiry,
            knowledge_result.get("context_string", ""),
            "resolve",
        )

        self.delegate_task(
            "Escalation Agent",
            "Sentiment Analysis Agent",
            "Review response confidence and sentiment for escalation decision",
            {
                "response_confidence": response_result["confidence"],
                "sentiment": sentiment_result["sentiment"],
            },
        )

        escalation_result = self.execute_tool(
            "escalation_agent",
            response_result["confidence"],
            sentiment_result["sentiment"],
            knowledge_result["count"],
            inquiry,
            sentiment_result.get("urgency", "Low"),
        )

        # Store in memory if enabled
        if ENABLE_MEMORY:
            memory_service.store_interaction(
                inquiry=inquiry,
                category=classification_result["category"],
                sentiment=sentiment_result["sentiment"],
                escalation_required=escalation_result["escalation_required"],
                final_response=response_result["response"],
                reference_id=escalation_result.get("reference_id")
            )

        return {
            "category": classification_result["category"],
            "category_confidence": classification_result["confidence"],
            "sentiment": sentiment_result["sentiment"],
            "sentiment_confidence": sentiment_result["confidence"],
            "urgency": sentiment_result["urgency"],
            "articles": knowledge_result["articles"],
            "response": response_result["response"],
            "response_confidence": response_result["confidence"],
            "escalation_required": escalation_result["escalation_required"],
            "escalation_reason": escalation_result["reason"],
            "reference_id": escalation_result["reference_id"],
            "steps": self.steps,
            "knowledge_source": knowledge_result.get("source", "unknown"),
            "memory_saved": ENABLE_MEMORY,
            "execution_mode": DEFAULT_CONFIG["execution_mode"],
        }





class SupportFlow(Flow[SupportState]):
    def __init__(self):
        super().__init__(tracing=True)
        self.steps: list[dict[str, Any]] = []
        self._start_time: float = time.time()
        self._cache_hit: bool = False
        self._inquiry_hash: str = ''

    def log_step(self, agent_name: str, details: dict[str, Any]) -> None:
        self.steps.append({
            "agent": agent_name,
            "timestamp": datetime.now().isoformat(),
            "elapsed_ms": round(
                (time.time() - self._start_time) * 1000
            ) if hasattr(self, '_start_time') else 0,
            "details": details
        })

    async def execute_tool(self, tool_name: str, *args, **kwargs) -> dict[str, Any]:
        """Execute tool through registry with logging."""
        start_timestamp = datetime.now().isoformat()
        t0 = time.time()
        result = await asyncio.to_thread(tool_registry.execute_tool, tool_name, *args, **kwargs)
        end_timestamp = datetime.now().isoformat()
        self.log_step(f"{tool_name} Agent", {
            "tool_used": tool_name,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "input_summary": str(args)[:300],
            "output_summary": str(result)[:300],
            "cached": result.get("cached", False),
            "execution_time": result.get("execution_time", 0),
            "execution_mode": result.get("execution_mode"),
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "total_tokens": result.get("total_tokens"),
            "cost_usd": result.get("cost_usd"),
        })
        observability_service.record_tool_execution(
            reference_id=self.state.run_id,
            agent_name=f"{tool_name} Agent",
            tool_name=tool_name,
            start_time=t0,
            input_summary=str(args)[:200],
            output_summary=str(result)[:200],
            status="success",
            confidence=float(result.get("confidence", 0)),
            execution_mode=result.get("execution_mode", "deterministic"),
            llm_used=result.get("execution_mode") == "llm",
            cache_used=bool(result.get("cached", False)),
            knowledge_sources=result.get("sources_used", []),
            estimated_tokens=result.get("estimated_context_tokens", 0),
            cost_usd=float(result.get("cost_usd", 0.0)),
            input_tokens=result.get("input_tokens", 0),
            output_tokens=result.get("output_tokens", 0),
            total_tokens=result.get("total_tokens", 0),
        )
        return result

    @start()
    async def classify_inquiry(self):
        self._start_time = time.time()
        self.steps = []
        # --- Response cache check ---
        inquiry_hash = hashlib.md5(
            self.state.inquiry.lower().strip().encode()
        ).hexdigest()[:8]
        self._inquiry_hash = inquiry_hash
        cached_entry = _response_cache.get(inquiry_hash)
        if cached_entry and (time.time() - cached_entry['ts'] < 300):
            logger.info(f"Cache hit for inquiry hash: {inquiry_hash}")
            for k, v in cached_entry['state'].items():
                setattr(self.state, k, v)
            self.state.cache_used = True
            self._cache_hit = True
            return "Cache hit"
        # --- Normal path ---
        result = await self.execute_tool("Classification Tool", self.state.inquiry)
        self.state.category = result["category"]
        self.state.category_confidence = result["confidence"]
        self.state.tools_used.append("Classification Tool")
        self.state.cache_used = result.get("cached", False)
        return f"Classified inquiry as {self.state.category}"

    @staticmethod
    def _is_portuguese(text: str) -> bool:
        import re as _re
        pt_indicators = {
            "meu", "minha", "não", "nao", "quero", "preciso",
            "pedido", "ajuda", "problema", "como", "obrigado",
            "produto", "conta", "fatura", "chegou", "comprei",
            "recebi", "estou", "qual", "política", "politica",
            "prazo", "entrega", "cancelar", "cancelamento",
            "devolução", "devolucao", "reembolso", "estorno",
        }
        en_indicators = {
            "my", "your", "what", "how", "where", "when", "why",
            "please", "help", "want", "need", "order", "return",
            "policy", "refund", "account", "issue", "problem",
            "cannot", "the", "this", "that", "have", "has",
            "not", "arrived", "i", "we", "is", "are",
        }
        words = set(_re.split(r"\W+", text.lower()))
        pt_score = len(words & pt_indicators)
        en_score = len(words & en_indicators)
        return pt_score > en_score

    @start()
    async def analyze_sentiment(self):
        if self._cache_hit:
            return "Skipped (cache hit)"
        result = await self.execute_tool("Sentiment Analysis Tool", self.state.inquiry)
        self.state.sentiment = result["sentiment"]
        self.state.sentiment_confidence = result["confidence"]
        self.state.urgency = result["urgency"]
        self.state.tools_used.append("Sentiment Analysis Tool")
        self.state.cache_used = self.state.cache_used or result.get("cached", False)
        return f"Analyzed sentiment as {self.state.sentiment}"

    @listen(and_(classify_inquiry, analyze_sentiment))
    async def route_inquiry(self):
        decision = route_ticket(
            inquiry=self.state.inquiry,
            category=self.state.category,
            sentiment=self.state.sentiment,
            urgency=self.state.urgency,
        )
        self.state.routing_action = decision.action
        self.state.routing_reason = decision.reason
        self.state.routing_missing_info = decision.missing_info
        self.state.routing_confidence = decision.confidence
        if decision.triggered_keyword:
            self.state.triggered_keyword = decision.triggered_keyword

        # If refund intent + order number in the inquiry, always defer to the
        # refund lookup tool regardless of the routing engine's decision
        # (catches both "awaiting" and billing "escalate" cases).
        import re as _re
        _has_refund_intent = is_refund_inquiry(self.state.inquiry)
        _has_order = bool(_re.search(r'\b\d{4,12}\b', self.state.inquiry))
        if _has_refund_intent and _has_order:
            self.state.routing_action = "pending_lookup"
            self.state.escalation_required = False

        self.log_step("Routing Engine", {
            "action": self.state.routing_action,
            "reason": decision.reason,
            "missing_info": decision.missing_info,
            "has_order_number": decision.has_order_number,
            "has_email": decision.has_email,
            "explicit_escalation": decision.explicit_escalation,
            "confidence": decision.confidence,
        })
        return f"Routed as: {self.state.routing_action}"

    @listen(route_inquiry)
    async def retrieve_knowledge(self):
        result = await self.execute_tool("Knowledge Retrieval Tool", self.state.category, self.state.inquiry)
        self.state.articles = result["articles"]
        self.state.knowledge_source = result.get("source", "unknown")
        self.state.knowledge_context = result.get("context_string", "")
        self.state.knowledge_sources = result.get("sources_used", [])
        self.state.estimated_context_tokens = result.get("estimated_context_tokens", 0)
        self.state.tools_used.append("Knowledge Retrieval Tool")
        self.state.cache_used = self.state.cache_used or result.get("cached", False)
        return f"Retrieved {len(self.state.articles)} knowledge articles from {self.state.knowledge_source}"

    @listen(retrieve_knowledge)
    async def enrich_with_external_data(self):
        import re
        from .routing_engine import check_logistics_alert, check_weather_delay
        print(f"DEBUG enrich_with_external_data: inquiry={self.state.inquiry[:50]}")
        print(f"DEBUG external_context before: '{self.state.external_context}'")

        if not ENABLE_EXTERNAL_APIS:
            print("DEBUG enrich_with_external_data: ENABLE_EXTERNAL_APIS=False, skipping")
            return "Skipped (external APIs disabled)"

        context_parts = []

        # ── CEP → address validation + logistics alert ──
        cep_match = re.search(r'\b(\d{5}-?\d{3})\b', self.state.inquiry)
        if cep_match:
            cep = cep_match.group(1)
            addr_result = await self.execute_tool("Address Validation Tool", cep)
            self.state.tools_used.append("Address Validation Tool")
            if addr_result.get("valid"):
                self.state.api_tags.append("cep_validated")
                state_code = addr_result.get("state", "")
                formatted = addr_result.get("formatted") or (
                    f"{addr_result.get('street')}, {addr_result.get('neighborhood')}, "
                    f"{addr_result.get('city')} - {addr_result.get('state')}"
                )
                alert = check_logistics_alert(state_code)
                print(f"DEBUG CEP result: state={state_code}, valid=True")
                print(f"DEBUG logistics alert: {alert}")
                if alert:
                    self.state.logistics_alert = alert
                    self.state.api_tags.append("logistics_alert")
                    context_parts.append(
                        f"Validated address: {formatted}"
                        f"\nLOGISTICS ALERT ACTIVE for {state_code}: "
                        f"Fleet maintenance causing 3-day delay in this region."
                    )
                    self.log_step("Address Validation Agent", {
                        "cep_valid": True,
                        "address": formatted,
                        "state": state_code,
                        "logistics_alert": True,
                        "alert_key": alert["alert_key"],
                    })
                else:
                    context_parts.append(
                        f"Validated address: {formatted}"
                        f"\nNo logistics alerts for {state_code}."
                    )
                    self.log_step("Address Validation Agent", {
                        "cep_valid": True,
                        "address": formatted,
                        "state": state_code,
                        "logistics_alert": False,
                    })
            else:
                print(f"DEBUG CEP result: valid=False, error={addr_result.get('error', addr_result.get('error_type', 'unknown'))}, logistics_alert=N/A")
            if addr_result.get("fallback"):
                context_parts.append(f"Address validation: {addr_result.get('fallback')}")

        # ── City → weather check + weather delay ──
        city_match = re.search(
            r'\b(São Paulo|Rio de Janeiro|Belo Horizonte|Curitiba|Porto Alegre|'
            r'Florianópolis|Florianopolis|Joinville|Blumenau|Caxias do Sul|'
            r'Salvador|Fortaleza|Recife|Manaus|Brasília|Brasilia|Goiânia|Goiania|Belém|Belem)\b',
            self.state.inquiry, re.IGNORECASE
        )
        if city_match:
            detected_city = city_match.group(1)
            weather_result = await self.execute_tool("Weather Check Tool", detected_city)
            self.state.tools_used.append("Weather Check Tool")
            if weather_result.get("available"):
                self.state.api_tags.append("weather_checked")
                weather_delay = check_weather_delay(detected_city, weather_result)
                if weather_delay:
                    self.state.weather_delay = weather_delay
                    self.state.api_tags.append("weather_alert")
                    context_parts.append(
                        f"WEATHER DELAY ALERT: "
                        f"{weather_result['conditions']} in {detected_city} "
                        f"({weather_result['temperature_c']}°C). "
                        f"Adverse conditions affecting deliveries."
                    )
                else:
                    context_parts.append(
                        f"Weather in {detected_city}: "
                        f"{weather_result.get('conditions', 'normal')}, "
                        f"{weather_result.get('temperature_c', '')}°C. "
                        f"No weather delays."
                    )

        # ── Refund status lookup ──
        has_refund_intent = is_refund_inquiry(self.state.inquiry)
        print(f"DEBUG enrich: has_refund_intent={has_refund_intent}")
        print(f"DEBUG enrich: routing_action={self.state.routing_action}")
        if has_refund_intent:
            order_num = extract_order_number(self.state.inquiry)
            if order_num:
                is_pt = self._is_portuguese(self.state.inquiry)
                refund_result = await asyncio.to_thread(
                    tool_registry.execute_tool, "Refund Status Tool", order_num
                )
                self.state.tools_used.append("Refund Status Tool")
                self.state.refund_data = refund_result
                self.state.api_tags.append("refund_lookup")
                if refund_result.get("found"):
                    self.state.api_tags.append("refund_found")
                    refund_details = [f"REFUND DATA FOUND - Pedido {order_num}:"]
                    refund_details.append(f"Status: {refund_result.get('status', '')}")
                    if refund_result.get("amount"):
                        refund_details.append(f"Amount: {refund_result['amount']}")
                    if refund_result.get("product_name"):
                        refund_details.append(f"Product: {refund_result['product_name']}")
                    if refund_result.get("approval_date"):
                        refund_details.append(f"Approval date: {refund_result['approval_date']}")
                    if refund_result.get("bank_deadline"):
                        refund_details.append(f"Bank deadline: {refund_result['bank_deadline']}")
                    if refund_result.get("eta_days"):
                        refund_details.append(f"ETA: {refund_result['eta_days']} business days")
                    context_parts.append("\n".join(refund_details))
                else:
                    msg = refund_result.get("message_pt" if is_pt else "message_en", "")
                    if msg:
                        context_parts.append(f"REFUND NOT FOUND (pedido {order_num}): {msg}")
                if refund_result.get("should_escalate"):
                    self.state.api_tags.append("refund_denied")
                self.log_step("Refund Status Agent", {
                    "order_number": order_num,
                    "refund_status": refund_result.get("status"),
                    "found": refund_result.get("found"),
                    "auto_resolve": refund_result.get("auto_resolve"),
                    "should_escalate": refund_result.get("should_escalate"),
                })

        self.state.external_context = "\n".join(context_parts)
        print(f"DEBUG external_context after: '{self.state.external_context}'")
        return f"External enrichment done: {len(context_parts)} data point(s)"

    @listen(enrich_with_external_data)
    async def generate_response(self):
        # Simulate agent collaboration
        self.log_step("Response Generation Agent", {
            "collaboration": "ask",
            "target_agent": "Knowledge Retrieval Agent",
            "question": f"What articles are available for category '{self.state.category}'?",
            "context": {"current_category": self.state.category},
        })

        print(f"DEBUG knowledge_context: {bool(self.state.knowledge_context)}")
        print(f"DEBUG external_context: '{self.state.external_context}'")

        result = await self.execute_tool(
            "Response Generation Tool",
            self.state.category,
            self.state.urgency,
            len(self.state.articles),
            self.state.inquiry,
            self.state.knowledge_context,
            self.state.routing_action,
            self.state.external_context,
        )
        self.state.response = result["response"]
        self.state.response_confidence = result["confidence"]
        self.state.prompt_template_used = result.get("template_used")
        self.state.token_usage = result.get("token_usage", {})
        self.state.cost_usd = result.get("cost_usd", 0.0)
        self.state.tools_used.append("Response Generation Tool")

        self.log_step("Response Generation Agent", {
            "tool_used": "Response Generation Tool",
            "category": self.state.category,
            "urgency": self.state.urgency,
            "knowledge_context_used": bool(self.state.knowledge_context),
            "knowledge_sources": self.state.knowledge_sources,
            "estimated_context_tokens": self.state.estimated_context_tokens,
            "response_length": len(result.get("response", "")),
            "confidence": result.get("confidence", 0),
            "execution_mode": result.get("execution_mode", "unknown"),
            "input_tokens": result.get("input_tokens"),
            "output_tokens": result.get("output_tokens"),
            "total_tokens": result.get("total_tokens"),
            "cost_usd": result.get("cost_usd"),
        })

        # Validate response with skills
        skills_validation = skill_service.validate_response_with_skills(
            self.state.response, "response_agent"
        )
        self.state.skills_used.extend(skills_validation.get("skills_used", []))

        return f"Generated response with confidence {self.state.response_confidence}%"

    @listen(generate_response)
    async def evaluate_response_quality(self):
        """Cross-model quality evaluation: Sonnet judges Haiku responses."""
        # Skip if no substantive response yet (awaiting/missing-info cases have short canned messages)
        if not self.state.response or len(self.state.response) < 40:
            self.log_step("Quality Evaluator Agent", {
                "skipped": True,
                "reason": "no substantive response to evaluate",
            })
            return "Skipped: no response"

        # Skip explicit escalation-only paths (no AI response generated)
        if self.state.routing_action == "escalate" and not self.state.external_context:
            self.log_step("Quality Evaluator Agent", {
                "skipped": True,
                "reason": "escalated with no external context",
            })
            return "Skipped: pure escalation"

        try:
            evaluation = await asyncio.to_thread(
                quality_evaluator.evaluate,
                inquiry=self.state.inquiry,
                response=self.state.response,
                category=self.state.category,
                routing_action=self.state.routing_action,
                knowledge_context=self.state.knowledge_context,
                external_context=self.state.external_context,
            )

            self.state.quality_evaluation = evaluation

            self.log_step("Quality Evaluator Agent", {
                "judge_model": evaluation.get("judge_model"),
                "response_model": evaluation.get("response_model"),
                "overall": evaluation.get("overall"),
                "grade": evaluation.get("grade"),
                "faithfulness": evaluation.get("faithfulness"),
                "relevance": evaluation.get("relevance"),
                "empathy": evaluation.get("empathy"),
                "completeness": evaluation.get("completeness"),
                "hallucination_detected": evaluation.get("hallucination_detected"),
                "hallucination_details": evaluation.get("hallucination_details"),
                "issues": evaluation.get("issues", []),
                "suggestion": evaluation.get("suggestion"),
                "cost_usd": evaluation.get("cost_usd", 0),
                "latency_ms": evaluation.get("latency_ms", 0),
            })

            return (
                f"Evaluated: grade={evaluation.get('grade', '?')} "
                f"overall={evaluation.get('overall', 0)} "
                f"hallucination={evaluation.get('hallucination_detected', False)}"
            )

        except Exception as e:
            logger.error("Quality evaluation failed: %s", e)
            return f"Evaluation failed: {e}"

    @listen(evaluate_response_quality)
    async def evaluate_escalation(self):
        print(f"DEBUG evaluate_escalation:")
        print(f"  routing_action: {self.state.routing_action}")
        print(f"  refund_data: {self.state.refund_data}")
        print(f"  logistics_alert: {self.state.logistics_alert}")
        print(f"  weather_delay: {self.state.weather_delay}")
        print(f"  escalation_required: {self.state.escalation_required}")
        print(f"  external_context: '{self.state.external_context[:100]}'")
        # Simulate agent collaboration
        self.log_step("Escalation Agent", {
            "collaboration": "delegate",
            "target_agent": "Sentiment Analysis Agent",
            "task": "Review response confidence and sentiment for escalation decision",
            "context": {
                "response_confidence": self.state.response_confidence,
                "sentiment": self.state.sentiment,
            },
        })

        result = await self.execute_tool(
            "Escalation Evaluation Tool",
            self.state.response_confidence,
            self.state.sentiment,
            len(self.state.articles),
            self.state.inquiry,
            self.state.urgency,
        )
        self.state.escalation_required = result["escalation_required"]
        self.state.escalation_reason = result["reason"]
        self.state.reference_id = result["reference_id"]
        if result.get("triggered_keyword") and not self.state.triggered_keyword:
            self.state.triggered_keyword = result.get("triggered_keyword")
        self.state.tools_used.append("Escalation Evaluation Tool")

        # Re-key observability events from run_id to the final reference_id
        if self.state.reference_id and self.state.run_id:
            observability_service.remap_events(self.state.run_id, self.state.reference_id)

        # Validate escalation with skills
        escalation_skills = skill_service.validate_response_with_skills(
            f"Escalation decision: {self.state.escalation_reason}", "escalation_agent"
        )
        self.state.skills_used.extend(escalation_skills.get("skills_used", []))

        # ── Priority chain: external alerts first, routing decision last ──
        print(f"DEBUG escalation: refund_data={self.state.refund_data}")
        print(f"DEBUG escalation: routing_action={self.state.routing_action}")

        if self.state.logistics_alert and self.state.logistics_alert.get("alert_active"):
            # PRIORITY 1: logistics alert — LLM already generated response using external_context
            alert = self.state.logistics_alert
            self.state.escalation_required = False
            self.state.routing_action = "resolve"
            self.state.auto_resolve_reason = "logistics_alert"
            self.log_step("Routing Engine", {
                "override": "logistics_alert",
                "reason": "Active logistics delay — auto-resolved",
                "alert_key": alert.get("alert_key"),
                "auto_resolved": True,
            })

        elif self.state.weather_delay and self.state.weather_delay.get("delay_active"):
            # PRIORITY 2: weather delay — LLM already generated response using external_context
            self.state.escalation_required = False
            self.state.routing_action = "resolve"
            self.state.auto_resolve_reason = "weather_delay"
            self.log_step("Routing Engine", {
                "override": "weather_delay",
                "reason": "Adverse weather — auto-resolved",
                "auto_resolved": True,
            })

        elif (self.state.refund_data.get("found") and
              self.state.refund_data.get("auto_resolve")):
            # PRIORITY 3: refund found + auto-resolvable — LLM generated response via REFUND DATA FOUND context
            refund_status = self.state.refund_data.get("status")
            self.state.escalation_required = False
            self.state.routing_action = "resolve"
            self.state.auto_resolve_reason = "refund_found"
            self.log_step("Routing Engine", {
                "override": "refund_status",
                "refund_status": refund_status,
                "auto_resolved": True,
            })

        elif self.state.refund_data.get("should_escalate"):
            # PRIORITY 4: refund found + denied → route to human
            refund_status = self.state.refund_data.get("status")
            is_pt = self._is_portuguese(self.state.inquiry)
            msg = self.state.refund_data.get(
                "message_pt" if is_pt else "message_en", ""
            )
            self.state.escalation_required = True
            self.state.routing_action = "escalate"
            self.state.escalation_reason = (
                "Reembolso negado — requer explicação e revisão humana"
                if is_pt else
                "Refund denied — requires human explanation and review"
            )
            if msg:
                self.state.response = msg
            self.log_step("Routing Engine", {
                "override": "refund_status",
                "refund_status": refund_status,
                "auto_resolved": False,
                "hitl": True,
            })

        else:
            # PRIORITY 5: routing engine decision (no external alert / refund match)
            if self.state.routing_action == "escalate":
                self.state.escalation_required = True
                self.state.escalation_reason = self.state.routing_reason

            elif self.state.routing_action == "pending_lookup":
                is_pt = self._is_portuguese(self.state.inquiry)
                _rd = self.state.refund_data
                if _rd.get("found") and _rd.get("auto_resolve"):
                    # Safety net: lookup found auto-resolvable refund
                    _msg = _rd.get("message_pt" if is_pt else "message_en", "")
                    self.state.escalation_required = False
                    self.state.routing_action = "resolve"
                    if _msg:
                        self.state.response = _msg
                elif _rd.get("should_escalate"):
                    # Safety net: lookup found denied refund
                    _msg = _rd.get("message_pt" if is_pt else "message_en", "")
                    self.state.escalation_required = True
                    self.state.routing_action = "escalate"
                    self.state.escalation_reason = (
                        "Reembolso negado — requer explicação e revisão humana"
                        if is_pt else
                        "Refund denied — requires human explanation and review"
                    )
                    if _msg:
                        self.state.response = _msg
                else:
                    # Refund not found → route to human for manual investigation
                    self.state.escalation_required = True
                    self.state.routing_action = "escalate"
                    self.state.escalation_reason = (
                        "Reembolso não localizado — requer verificação manual"
                        if is_pt else
                        "Refund not found — requires manual investigation"
                    )

            elif self.state.routing_action == "awaiting":
                self.state.escalation_required = True
                self.state.escalation_reason = (
                    f"Awaiting customer information: "
                    f"{', '.join(self.state.routing_missing_info)}"
                )
                missing = self.state.routing_missing_info
                pt = self._is_portuguese(self.state.inquiry)
                if "order_number" in missing and "email" in missing:
                    self.state.response = (
                        "Entendo sua situação e quero ajudá-la o mais rápido possível! "
                        "Para isso, preciso de algumas informações:\n\n"
                        "1. Número do pedido\n"
                        "2. E-mail cadastrado na conta\n\n"
                        "Assim que receber essas informações, encaminharei para nossa equipe especializada."
                    ) if pt else (
                        "I'd love to help resolve this quickly! To proceed, I need:\n\n"
                        "1. Your order number\n"
                        "2. Email address on the account\n\n"
                        "Once I have these details, I'll route your case to our specialist team immediately."
                    )
                elif "order_number" in missing:
                    self.state.response = (
                        "Para localizar seu pedido e ajudá-la, preciso do número do pedido. "
                        "Você pode encontrá-lo no e-mail de confirmação da compra. Pode me informar?"
                    ) if pt else (
                        "To locate your order and help you, I need your order number. "
                        "You can find it in your purchase confirmation email. Could you share it?"
                    )
                elif "screenshot_or_description" in missing:
                    self.state.response = (
                        "Para diagnosticar o problema técnico, pode me fornecer:\n\n"
                        "1. Um screenshot do erro (se possível)\n"
                        "2. Qual navegador e dispositivo está usando\n"
                        "3. Mensagem de erro exata (se aparecer)\n\n"
                        "Com essas informações consigo ajudá-la melhor!"
                    ) if pt else (
                        "To diagnose the technical issue, could you provide:\n\n"
                        "1. A screenshot of the error (if possible)\n"
                        "2. Which browser and device you're using\n"
                        "3. The exact error message (if any)\n\n"
                        "This will help me assist you better!"
                    )

            elif self.state.routing_action in ("step_by_step", "resolve"):
                self.state.escalation_required = False

        # ── Append escalation notice to response ──
        if self.state.escalation_required and self.state.routing_action != "awaiting":
            if _is_portuguese(self.state.inquiry):
                self.state.response += (
                    "\n\nSua solicitação foi encaminhada para análise humana. "
                    "Um agente de suporte entrará em contato em até 24 horas."
                )
                if self.state.reference_id:
                    self.state.response += f"\n\nID de Referência: {self.state.reference_id}"
            else:
                self.state.response += (
                    "\n\nYour inquiry has been flagged for human review. "
                    "A support agent will contact you within 24 hours to assist you further."
                )
                if self.state.reference_id:
                    self.state.response += f"\n\nReference ID: {self.state.reference_id}"

        # Store in memory if enabled
        if ENABLE_MEMORY:
            memory_result = await asyncio.to_thread(tool_registry.execute_tool, "Memory Management Tool", "store",
                inquiry=self.state.inquiry,
                category=self.state.category,
                sentiment=self.state.sentiment,
                escalation_required=self.state.escalation_required,
                response=self.state.response,
                reference_id=self.state.reference_id
            )
            self.state.memory_saved = memory_result.get("success", False)
            self.state.tools_used.append("Memory Management Tool")

        self.state.execution_mode = DEFAULT_CONFIG["execution_mode"]
        self.state.steps = self.steps

        # Populate response cache for identical future inquiries
        if self._inquiry_hash and not self._cache_hit:
            _response_cache[self._inquiry_hash] = {
                'ts': time.time(),
                'state': {
                    'category': self.state.category,
                    'category_confidence': self.state.category_confidence,
                    'sentiment': self.state.sentiment,
                    'sentiment_confidence': self.state.sentiment_confidence,
                    'urgency': self.state.urgency,
                    'articles': list(self.state.articles),
                    'response': self.state.response,
                    'response_confidence': self.state.response_confidence,
                    'escalation_required': self.state.escalation_required,
                    'escalation_reason': self.state.escalation_reason,
                }
            }

        return f"Escalation {'required' if self.state.escalation_required else 'not required'}"


app = FastAPI(
    title="AAMAD Support Backend",
    description="Backend API for the CrewAI multi-agent support interface.",
    version="0.1.0",
)

ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:5500,http://127.0.0.1:5500,http://localhost:3000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-API-Key"],
)

# Initialize services
knowledge_service = KnowledgeService()
memory_service = MemoryService()
prompt_service = PromptService()
skill_service = SkillService()
observability_service = ObservabilityService()

# Dataset mode: "live" reads from tickets.db, "historical" reads from demo_dataset.db (read-only)
_dataset_mode = "live"


def _get_demo_tickets() -> List[SupportTicketData]:
    """Read tickets from demo_dataset.db without touching the live database."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from pathlib import Path as _Path

    demo_db = _Path("src/aamad/data/demo_dataset.db")
    if not demo_db.exists():
        return []
    try:
        engine = create_engine(f"sqlite:///{demo_db}")
        DemoSession = sessionmaker(bind=engine)
        session = DemoSession()
        try:
            rows = session.query(SupportTicketDB).order_by(SupportTicketDB.created_at.desc()).all()
            return [data_store._db_to_pydantic(r) for r in rows]
        finally:
            session.close()
    except Exception as _e:
        logger.error(f"Error reading demo dataset: {_e}")
        return []


def _get_ticket_count(mode: str) -> int:
    """Get ticket count for a given mode without side effects."""
    from sqlalchemy import create_engine, text as _text
    from pathlib import Path as _Path

    try:
        if mode == "historical":
            demo_db = _Path("src/aamad/data/demo_dataset.db")
            if not demo_db.exists():
                return 0
            engine = create_engine(f"sqlite:///{demo_db}")
            with engine.connect() as conn:
                return conn.execute(_text("SELECT COUNT(*) FROM support_tickets")).scalar() or 0
        else:
            with data_store.SessionLocal() as session:
                from sqlalchemy import text as _text2
                return session.execute(_text2("SELECT COUNT(*) FROM support_tickets")).scalar() or 0
    except Exception:
        return 0


# Initialize integration clients (mock)
ticketing_client = TicketingClient()
crm_client = CRMClient()
notification_client = NotificationClient()

# Initialize tool registry
tool_registry = ToolRegistry()
tool_registry.register_tool(ClassificationTool)
tool_registry.register_tool(SentimentTool)
tool_registry.register_tool(KnowledgeTool, "Knowledge Retrieval Tool")
tool_registry.register_tool(ResponseTool)
tool_registry.register_tool(EscalationTool)
tool_registry.register_tool(MemoryTool)
tool_registry.register_tool(PromptTool)
tool_registry.register_tool(RESTApiTool, "REST API Tool")
tool_registry.register_tool(GraphQLApiTool, "GraphQL API Tool")
tool_registry.register_tool(WeatherTool)
tool_registry.register_tool(GitHubTool)
tool_registry.register_tool(AddressValidationTool, "Address Validation Tool")
tool_registry.register_tool(WeatherCheckTool, "Weather Check Tool")
tool_registry.register_tool(RefundLookupTool, "Refund Status Tool")

# Inject services into tools that need them
tool_registry.tools["Knowledge Retrieval Tool"].knowledge_service = knowledge_service
tool_registry.tools["Memory Management Tool"].memory_service = memory_service
tool_registry.tools["Prompt Management Tool"].prompt_service = prompt_service

# In-memory metrics store (keyed by reference_id)
_metrics_store: Dict[str, RunMetrics] = {}

# Response cache: hash → {ts, state_snapshot} — expires after 300 s
_response_cache: Dict[str, Dict[str, Any]] = {}


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aamad backend"}


@app.post("/api/support", response_model=SupportResponse)
async def create_support_ticket(ticket: SupportTicket) -> SupportResponse:
    inquiry = ticket.inquiry.strip()
    if not inquiry:
        raise HTTPException(status_code=400, detail="Inquiry text cannot be empty.")

    run_id = str(uuid.uuid4())
    start_time = time.time()

    # Process the support request through the CrewAI flow
    support_flow = SupportFlow()
    await support_flow.kickoff_async({"inquiry": inquiry, "run_id": run_id})
    # Unwrap the StateProxy so Pydantic/pydantic-core sees real Python lists,
    # not LockedListProxy (whose C-level list buffer is always empty).
    final_state = support_flow.state._unwrap()

    wall_time = round(time.time() - start_time, 3)
    execution_time_ms = int(wall_time * 1000)

    # Generate reference ID
    reference_id = final_state.reference_id if final_state.escalation_required else f"REF-{int(time.time())}"

    # Determine status based on routing action and escalation
    if final_state.routing_action == "awaiting":
        status = "awaiting_customer_info"
    elif final_state.escalation_required:
        status = "pending_human_review"
    else:
        status = "completed"

    # Capture RunMetrics and store in memory
    metrics = RunMetrics(
        run_id=run_id,
        reference_id=reference_id,
        status=status,
        started_at=start_time,
        finished_at=time.time(),
        wall_time_sec=wall_time,
        step_count=len(final_state.steps),
        tool_latency_ms={
            step["agent"]: step.get("elapsed_ms", 0)
            for step in final_state.steps
        },
        token_usage={},
        success_rate=1.0 if not final_state.escalation_required else 0.8,
    )
    _metrics_store[reference_id] = metrics

    # Create ticket data for persistence
    ticket_data = SupportTicketData(
        reference_id=reference_id,
        inquiry=inquiry,
        category=final_state.category,
        category_confidence=final_state.category_confidence,
        sentiment=final_state.sentiment,
        sentiment_confidence=final_state.sentiment_confidence,
        urgency=final_state.urgency,
        articles=final_state.articles,
        response=final_state.response,
        response_confidence=final_state.response_confidence,
        escalation_required=final_state.escalation_required,
        escalation_reason=final_state.escalation_reason,
        triggered_keyword=final_state.triggered_keyword,
        steps=final_state.steps,
        knowledge_source=final_state.knowledge_source,
        memory_saved=final_state.memory_saved,
        execution_mode=final_state.execution_mode,
        prompt_template_used=final_state.prompt_template_used,
        skills_used=final_state.skills_used,
        tools_used=final_state.tools_used,
        cache_used=final_state.cache_used,
        status=status,
        created_at=datetime.now().isoformat(),
        updated_at=datetime.now().isoformat(),
        run_id=run_id,
        execution_time_ms=execution_time_ms,
        wall_time_sec=wall_time,
        token_usage=final_state.token_usage,
        cost_usd=final_state.cost_usd,
        api_tags=final_state.api_tags,
        quality_evaluation=final_state.quality_evaluation or {},
    )

    # Save to data store
    data_store.save_ticket(ticket_data)

    # Handle integrations if enabled
    if ENABLE_MOCK_INTEGRATIONS:
        try:
            # Create external ticket if escalated
            if final_state.escalation_required:
                external_ticket = ticketing_client.create_ticket({
                    "inquiry": inquiry,
                    "category": final_state.category,
                    "urgency": final_state.urgency,
                    "reference_id": reference_id
                })
                # Send notification to support team
                notification_client.send_support_notification(
                    "support@company.com",
                    ticket_data.model_dump()
                )

            # Send confirmation to customer (mock email)
            notification_client.send_customer_notification(
                "customer@example.com",  # Would be extracted from inquiry
                ticket_data.model_dump()
            )

        except Exception as e:
            logger.error("Integration error: %s", e)

    # Build response model with the same fields
    response = SupportResponse(
        inquiry=inquiry,
        category=final_state.category,
        category_confidence=final_state.category_confidence,
        sentiment=final_state.sentiment,
        sentiment_confidence=final_state.sentiment_confidence,
        urgency=final_state.urgency,
        articles=final_state.articles,
        response=final_state.response,
        response_confidence=final_state.response_confidence,
        escalation_required=final_state.escalation_required,
        escalation_reason=final_state.escalation_reason,
        reference_id=reference_id,
        triggered_keyword=final_state.triggered_keyword,
        steps=final_state.steps,
        knowledge_source=final_state.knowledge_source,
        memory_saved=final_state.memory_saved,
        execution_mode=final_state.execution_mode,
        prompt_template_used=final_state.prompt_template_used,
        tools_used=final_state.tools_used,
        skills_used=final_state.skills_used,
        cache_used=final_state.cache_used,
        run_id=run_id,
        wall_time_sec=wall_time,
        token_usage=final_state.token_usage or None,
        cost_usd=final_state.cost_usd or None,
        routing_action=final_state.routing_action or None,
        routing_reason=final_state.routing_reason or None,
        routing_missing_info=final_state.routing_missing_info or None,
        api_tags=final_state.api_tags or None,
        quality_evaluation=final_state.quality_evaluation or None,
    )

    return response


@app.get("/api/support/{reference_id}/status", response_model=StatusResponse)
async def get_ticket_status(reference_id: str) -> StatusResponse:
    """Get the status of a support ticket."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return StatusResponse(
        reference_id=ticket.reference_id,
        status=ticket.status,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
        escalation_required=ticket.escalation_required,
        escalation_reason=ticket.escalation_reason
    )


@app.get("/api/support/{reference_id}/steps", response_model=StepsResponse)
async def get_ticket_steps(reference_id: str) -> StepsResponse:
    """Get the execution steps of a support ticket."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return StepsResponse(
        reference_id=ticket.reference_id,
        steps=ticket.steps,
        status=ticket.status
    )


@app.get("/api/support/{reference_id}/trace", response_model=TraceResponse)
async def get_ticket_trace(reference_id: str, _=Depends(verify_api_key)) -> TraceResponse:
    """Get observability trace for a support ticket execution."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    return TraceResponse(
        reference_id=ticket.reference_id,
        run_id=ticket.run_id or "",
        steps=ticket.steps,
        total_steps=len(ticket.steps),
        execution_time_ms=ticket.execution_time_ms,
        tools_used=ticket.tools_used,
        tracing_enabled=True
    )


@app.get("/api/metrics/summary")
async def get_metrics_summary(_=Depends(verify_api_key)) -> Dict[str, Any]:
    """Aggregate performance metrics across all tickets in current dataset mode."""
    tickets = _get_demo_tickets() if _dataset_mode == "historical" else data_store.get_all_tickets()
    if not tickets:
        return {
            "total_runs": 0,
            "avg_wall_time_sec": 0.0,
            "success_rate": 1.0,
            "total_escalated": 0,
            "avg_step_count": 0.0,
            "slowest_tool": None,
            "fastest_run_sec": 0.0,
            "slowest_run_sec": 0.0,
            "csat_score": None,
            "helpful_count": 0,
            "not_helpful_count": 0,
            "total_feedback": 0,
            "feedback_rate": 0,
        }

    total = len(tickets)
    total_escalated = sum(1 for t in tickets if t.escalation_required)
    avg_wall_time = sum(t.execution_time_ms for t in tickets) / total / 1000
    success_rate = round((total - total_escalated) / total, 3)
    avg_step_count = round(sum(len(t.steps) for t in tickets) / total, 1)

    # Compute per-tool average latency from stored step details
    tool_times: Dict[str, list] = {}
    for ticket in tickets:
        for step in ticket.steps:
            details = step.get("details", {})
            tool = details.get("tool_used")
            exec_time = details.get("execution_time")
            if tool and exec_time:
                tool_times.setdefault(tool, []).append(float(exec_time))

    slowest_tool = None
    if tool_times:
        slowest_tool = max(tool_times, key=lambda t: sum(tool_times[t]) / len(tool_times[t]))

    run_times = [t.execution_time_ms / 1000 for t in tickets if t.execution_time_ms]
    fastest = round(min(run_times), 3) if run_times else 0.0
    slowest = round(max(run_times), 3) if run_times else 0.0

    # Aggregate CSAT from ticket feedback
    helpful_count = 0
    not_helpful_count = 0
    total_feedback = 0
    for ticket in tickets:
        feedback = getattr(ticket, "feedback", None) or {}
        if feedback:
            total_feedback += 1
            if feedback.get("helpful") is True:
                helpful_count += 1
            elif feedback.get("helpful") is False:
                not_helpful_count += 1

    csat_score = round((helpful_count / total_feedback) * 100) if total_feedback > 0 else None

    obs_summary = observability_service.get_summary()

    return {
        "total_runs": total,
        "avg_wall_time_sec": round(avg_wall_time, 3),
        "success_rate": success_rate,
        "total_escalated": total_escalated,
        "avg_step_count": avg_step_count,
        "slowest_tool": slowest_tool,
        "fastest_run_sec": fastest,
        "slowest_run_sec": slowest,
        "csat_score": csat_score,
        "helpful_count": helpful_count,
        "not_helpful_count": not_helpful_count,
        "total_feedback": total_feedback,
        "feedback_rate": round((total_feedback / total) * 100) if total > 0 else 0,
        "agent_performance": obs_summary.get("agent_performance", {}),
        "tool_usage": obs_summary.get("tool_usage", {}),
        "total_llm_calls": obs_summary.get("llm_calls", 0),
        "total_events": obs_summary.get("total_events", 0),
        "avg_tool_latency_ms": obs_summary.get("avg_latency_ms", 0),
        "total_real_cost_usd": obs_summary.get("total_cost_usd", 0.0),
    }


@app.get("/api/support/{reference_id}/metrics", response_model=RunMetrics)
async def get_ticket_metrics(reference_id: str, _=Depends(verify_api_key)) -> RunMetrics:
    """Return RunMetrics for a specific ticket (in-memory, current session only)."""
    if reference_id not in _metrics_store:
        raise HTTPException(status_code=404, detail="Metrics not found for this ticket")
    return _metrics_store[reference_id]


@app.get("/api/observability/summary")
async def get_observability_summary(_=Depends(verify_api_key)) -> dict:
    """Get aggregate observability metrics."""
    return observability_service.get_summary()


@app.get("/api/observability/tickets/{reference_id}")
async def get_ticket_observability(
    reference_id: str,
    _=Depends(verify_api_key),
) -> dict:
    """Get structured observability events for a ticket."""
    events = observability_service.get_events(reference_id)
    if not events:
        raise HTTPException(
            status_code=404,
            detail="No observability events found for this ticket",
        )
    return {
        "reference_id": reference_id,
        "events": events,
        "total_events": len(events),
        "total_latency_ms": sum(e["latency_ms"] for e in events),
        "llm_calls": sum(1 for e in events if e["llm_used"]),
        "total_tokens": sum(e["estimated_tokens"] for e in events),
    }


@app.post("/api/support/{reference_id}/feedback")
async def submit_feedback(reference_id: str, feedback: FeedbackRequest):
    """Submit feedback for a support ticket."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Update ticket with feedback
    feedback_data = {
        "helpful": feedback.helpful,
        "comments": feedback.comments,
        "approval_status": feedback.approval_status,
        "submitted_at": datetime.now().isoformat()
    }

    data_store.update_ticket_status(reference_id, ticket.status, feedback_data)

    return {"message": "Feedback submitted successfully", "reference_id": reference_id}


@app.post("/api/support/{reference_id}/approve")
async def approve_ticket(reference_id: str, _=Depends(verify_api_key)):
    """Approve a support ticket (mark as resolved)."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "pending_human_review":
        raise HTTPException(status_code=400, detail="Ticket is not pending human review")

    data_store.update_ticket_status(reference_id, "approved")

    # Mock integration: update external ticket status
    if ENABLE_MOCK_INTEGRATIONS:
        try:
            ticketing_client.update_ticket_status(f"EXT-{reference_id}", "resolved")
        except Exception as e:
            logger.error("Integration error: %s", e)

    return {"message": "Ticket approved successfully", "reference_id": reference_id}


@app.post("/api/support/{reference_id}/reject")
async def reject_ticket(reference_id: str, _=Depends(verify_api_key)):
    """Reject a support ticket (requires revision)."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status != "pending_human_review":
        raise HTTPException(status_code=400, detail="Ticket is not pending human review")

    data_store.update_ticket_status(reference_id, "rejected")

    # Mock integration: update external ticket status
    if ENABLE_MOCK_INTEGRATIONS:
        try:
            ticketing_client.update_ticket_status(f"EXT-{reference_id}", "needs_revision")
        except Exception as e:
            logger.error("Integration error: %s", e)

    return {"message": "Ticket rejected and marked for revision", "reference_id": reference_id}


@app.post("/api/support/{reference_id}/await-customer")
async def await_customer_info(reference_id: str, _=Depends(verify_api_key)):
    """Mark ticket as awaiting customer information."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status not in ("pending_human_review", "awaiting_customer_info"):
        raise HTTPException(status_code=400, detail="Ticket cannot be set to awaiting from current status")

    data_store.update_ticket_status(reference_id, "awaiting_customer_info")
    return {"message": "Ticket awaiting customer response", "reference_id": reference_id}


@app.get("/api/tickets")
async def get_all_tickets_endpoint(_=Depends(verify_api_key)):
    """Get all tickets from the current dataset mode."""
    if _dataset_mode == "historical":
        tickets = _get_demo_tickets()
    else:
        tickets = data_store.get_all_tickets()
        tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)
    return [ticket.model_dump() for ticket in tickets]


@app.get("/api/dataset/mode")
async def get_dataset_mode():
    """Get current dataset mode and ticket counts for both modes."""
    from pathlib import Path as _Path
    return {
        "mode": _dataset_mode,
        "live_tickets": _get_ticket_count("live"),
        "historical_tickets": _get_ticket_count("historical"),
        "demo_dataset_exists": _Path("src/aamad/data/demo_dataset.db").exists(),
    }


@app.post("/api/dataset/mode")
async def set_dataset_mode(payload: dict, _=Depends(verify_api_key)):
    """Switch dataset mode. Historical mode reads demo_dataset.db (read-only)."""
    global _dataset_mode
    from pathlib import Path as _Path

    mode = payload.get("mode", "live")
    if mode not in ("live", "historical"):
        raise HTTPException(status_code=400, detail="Mode must be 'live' or 'historical'")

    if mode == "historical" and not _Path("src/aamad/data/demo_dataset.db").exists():
        raise HTTPException(status_code=404, detail="Demo dataset not found. Create demo_dataset.db first.")

    _dataset_mode = mode
    return {
        "success": True,
        "mode": _dataset_mode,
        "live_tickets": _get_ticket_count("live"),
        "historical_tickets": _get_ticket_count("historical"),
        "message": f"Switched to {mode} mode",
    }


@app.delete("/api/tickets/clear")
async def clear_tickets(_=Depends(verify_api_key)):
    """Delete all tickets and create an automatic backup first."""
    import shutil
    from pathlib import Path
    from sqlalchemy import text as sa_text

    db_path = Path("src/aamad/data/tickets.db")
    backup_path = None
    if db_path.exists():
        backup_name = (
            f"support_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        )
        backup_path = Path(f"src/aamad/data/{backup_name}")
        shutil.copy2(db_path, backup_path)

    with data_store.SessionLocal() as session:
        result = session.execute(sa_text("DELETE FROM support_tickets"))
        session.commit()
        deleted = result.rowcount

    return {
        "success": True,
        "deleted_tickets": deleted,
        "backup_created": str(backup_path) if backup_path else None,
        "backup_filename": backup_path.name if backup_path else None,
        "message": (
            f"Cleared {deleted} tickets. "
            f"Backup: {backup_path.name if backup_path else 'none'}"
        ),
    }


@app.get("/api/tickets/backups")
async def list_backups(_=Depends(verify_api_key)):
    """List all automatic database backups."""
    from pathlib import Path
    data_dir = Path("src/aamad/data")
    backups = sorted(data_dir.glob("support_backup_*.db"), reverse=True)
    return {
        "backups": [
            {
                "filename": b.name,
                "created_at": b.stem.replace("support_backup_", ""),
                "size_kb": round(b.stat().st_size / 1024, 1),
            }
            for b in backups
        ]
    }


@app.post("/api/tickets/restore")
async def restore_backup(payload: dict, _=Depends(verify_api_key)):
    """Restore the database from a named backup file."""
    import shutil
    from pathlib import Path

    backup_file = payload.get("backup_file")
    if not backup_file:
        raise HTTPException(status_code=400, detail="backup_file is required")
    backup_path = Path(f"src/aamad/data/{backup_file}")
    db_path = Path("src/aamad/data/tickets.db")
    if not backup_path.exists():
        raise HTTPException(status_code=404, detail=f"Backup {backup_file} not found")
    shutil.copy2(backup_path, db_path)
    return {
        "success": True,
        "restored_from": backup_file,
        "message": "Database restored successfully",
    }


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    uvicorn.run(
        "aamad.backend:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
