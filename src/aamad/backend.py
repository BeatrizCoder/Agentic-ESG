from crewai import Agent, Flow
from crewai.flow.flow import start, listen
from crewai.tools import BaseTool
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml
import random
import unicodedata
from typing import List, Dict, Any, Optional
import os
from dotenv import load_dotenv
import asyncio
import time
import uuid
from datetime import datetime

# Import new services and config
from .config import USE_LLM, ENABLE_MEMORY, ENABLE_CREWAI_KNOWLEDGE, DEFAULT_CONFIG, ENABLE_EXTERNAL_APIS, ENABLE_MOCK_INTEGRATIONS
from .services import KnowledgeService, MemoryService, PromptService, SkillService
from .tool_registry import ToolRegistry
from .data_store import data_store, SupportTicketData
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

# Load environment variables
load_dotenv()

# Load configuration
with open("config/agents.yaml", "r") as f:
    agents_config = yaml.safe_load(f)

with open("config/tasks.yaml", "r") as f:
    tasks_config = yaml.safe_load(f)

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
                verbose=True
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
        result = await asyncio.to_thread(tool_registry.execute_tool, tool_name, *args, **kwargs)
        end_timestamp = datetime.now().isoformat()
        self.log_step(f"{tool_name} Agent", {
            "tool_used": tool_name,
            "start_timestamp": start_timestamp,
            "end_timestamp": end_timestamp,
            "input_summary": str(args)[:300],
            "output_summary": str(result)[:300],
            "cached": result.get("cached", False),
            "execution_time": result.get("execution_time", 0)
        })
        return result

    @start()
    async def classify_inquiry(self):
        self._start_time = time.time()
        self.steps = []
        result = await self.execute_tool("Classification Tool", self.state.inquiry)
        self.state.category = result["category"]
        self.state.category_confidence = result["confidence"]
        self.state.tools_used.append("Classification Tool")
        self.state.cache_used = result.get("cached", False)
        return f"Classified inquiry as {self.state.category}"

    @listen(classify_inquiry)
    async def analyze_sentiment(self):
        result = await self.execute_tool("Sentiment Analysis Tool", self.state.inquiry)
        self.state.sentiment = result["sentiment"]
        self.state.sentiment_confidence = result["confidence"]
        self.state.urgency = result["urgency"]
        self.state.tools_used.append("Sentiment Analysis Tool")
        self.state.cache_used = self.state.cache_used or result.get("cached", False)
        return f"Analyzed sentiment as {self.state.sentiment}"

    @listen(analyze_sentiment)
    async def retrieve_knowledge(self):
        result = await self.execute_tool("Knowledge Retrieval Tool", self.state.category, self.state.inquiry)
        self.state.articles = result["articles"]
        self.state.knowledge_source = result.get("source", "unknown")
        self.state.tools_used.append("Knowledge Retrieval Tool")
        self.state.cache_used = self.state.cache_used or result.get("cached", False)
        return f"Retrieved {len(self.state.articles)} knowledge articles from {self.state.knowledge_source}"

    @listen(retrieve_knowledge)
    async def generate_response(self):
        # Simulate agent collaboration
        self.log_step("Response Generation Agent", {
            "collaboration": "ask",
            "target_agent": "Knowledge Retrieval Agent",
            "question": f"What articles are available for category '{self.state.category}'?",
            "context": {"current_category": self.state.category},
        })

        result = await self.execute_tool(
            "Response Generation Tool",
            self.state.category,
            self.state.urgency,
            len(self.state.articles),
            self.state.inquiry,
        )
        self.state.response = result["response"]
        self.state.response_confidence = result["confidence"]
        self.state.prompt_template_used = result.get("template_used")
        self.state.tools_used.append("Response Generation Tool")

        # Validate response with skills
        skills_validation = skill_service.validate_response_with_skills(
            self.state.response, "response_agent"
        )
        self.state.skills_used.extend(skills_validation.get("skills_used", []))

        return f"Generated response with confidence {self.state.response_confidence}%"

    @listen(generate_response)
    async def evaluate_escalation(self):
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
        )
        self.state.escalation_required = result["escalation_required"]
        self.state.escalation_reason = result["reason"]
        self.state.reference_id = result["reference_id"]
        self.state.triggered_keyword = result.get("triggered_keyword")
        self.state.tools_used.append("Escalation Evaluation Tool")

        # Validate escalation with skills
        escalation_skills = skill_service.validate_response_with_skills(
            f"Escalation decision: {self.state.escalation_reason}", "escalation_agent"
        )
        self.state.skills_used.extend(escalation_skills.get("skills_used", []))

        # Update response if escalation is required
        if self.state.escalation_required:
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
        return f"Escalation {'required' if self.state.escalation_required else 'not required'}"


app = FastAPI(
    title="AAMAD Support Backend",
    description="Backend API for the CrewAI multi-agent support interface.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
knowledge_service = KnowledgeService()
memory_service = MemoryService()
prompt_service = PromptService()
skill_service = SkillService()

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

# Inject services into tools that need them
tool_registry.tools["Knowledge Retrieval Tool"].knowledge_service = knowledge_service
tool_registry.tools["Memory Management Tool"].memory_service = memory_service
tool_registry.tools["Prompt Management Tool"].prompt_service = prompt_service

# In-memory metrics store (keyed by reference_id)
_metrics_store: Dict[str, RunMetrics] = {}


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

    # Determine status based on escalation
    status = "pending_human_review" if final_state.escalation_required else "completed"

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
        execution_time_ms=execution_time_ms
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
            # Log integration errors but don't fail the request
            print(f"Integration error: {e}")

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
async def get_ticket_trace(reference_id: str) -> TraceResponse:
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
async def get_metrics_summary() -> Dict[str, Any]:
    """Aggregate performance metrics across all tickets."""
    tickets = data_store.get_all_tickets()
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

    return {
        "total_runs": total,
        "avg_wall_time_sec": round(avg_wall_time, 3),
        "success_rate": success_rate,
        "total_escalated": total_escalated,
        "avg_step_count": avg_step_count,
        "slowest_tool": slowest_tool,
        "fastest_run_sec": fastest,
        "slowest_run_sec": slowest,
    }


@app.get("/api/support/{reference_id}/metrics", response_model=RunMetrics)
async def get_ticket_metrics(reference_id: str) -> RunMetrics:
    """Return RunMetrics for a specific ticket (in-memory, current session only)."""
    if reference_id not in _metrics_store:
        raise HTTPException(status_code=404, detail="Metrics not found for this ticket")
    return _metrics_store[reference_id]


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
async def approve_ticket(reference_id: str):
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
            print(f"Integration error: {e}")

    return {"message": "Ticket approved successfully", "reference_id": reference_id}


@app.post("/api/support/{reference_id}/reject")
async def reject_ticket(reference_id: str):
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
            print(f"Integration error: {e}")

    return {"message": "Ticket rejected and marked for revision", "reference_id": reference_id}


@app.post("/api/support/{reference_id}/await-customer")
async def await_customer_info(reference_id: str):
    """Mark ticket as awaiting customer information."""
    ticket = data_store.get_ticket(reference_id)
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if ticket.status not in ("pending_human_review", "awaiting_customer_info"):
        raise HTTPException(status_code=400, detail="Ticket cannot be set to awaiting from current status")

    data_store.update_ticket_status(reference_id, "awaiting_customer_info")
    return {"message": "Ticket awaiting customer response", "reference_id": reference_id}


@app.get("/api/tickets")
async def get_all_tickets_endpoint():
    """Get all tickets ordered by created_at descending."""
    tickets = data_store.get_all_tickets()
    sorted_tickets = sorted(tickets, key=lambda t: t.created_at, reverse=True)
    return [ticket.model_dump() for ticket in sorted_tickets]


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
