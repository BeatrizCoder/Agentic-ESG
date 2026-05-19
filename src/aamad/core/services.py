"""
Eagerly initialized singleton services — imported by both flow/ and api/.

All heavy objects (tool_registry, observability_service, etc.) are created
here at module import time so there is a single instance for the whole process.
backend.py imports this module, which triggers initialization; no further
setup is needed by callers.
"""

import logging
from typing import Dict, Any

from ..config import ENABLE_MEMORY, ENABLE_MOCK_INTEGRATIONS
from ..services import KnowledgeService, MemoryService, PromptService, SkillService
from ..observability import ObservabilityService
from ..tool_registry import ToolRegistry
from ..integrations.ticketing_client import TicketingClient
from ..integrations.crm_client import CRMClient
from ..integrations.notification_client import NotificationClient

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
from tools.refund_lookup_tool import RefundLookupTool

logger = logging.getLogger(__name__)

# ── Core services ─────────────────────────────────────────────────────────────
knowledge_service = KnowledgeService()
memory_service = MemoryService()
prompt_service = PromptService()
skill_service = SkillService()
observability_service = ObservabilityService()

# ── Integration clients (mock) ────────────────────────────────────────────────
ticketing_client = TicketingClient()
crm_client = CRMClient()
notification_client = NotificationClient()

# ── Tool registry ─────────────────────────────────────────────────────────────
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

# ── Runtime state shared across the process ───────────────────────────────────
# Response cache: inquiry_hash → {ts, state_snapshot} — expires after 300 s
response_cache: Dict[str, Dict[str, Any]] = {}

# In-memory metrics store (keyed by reference_id, current session only)
metrics_store: Dict[str, Any] = {}

# Dataset mode: "live" = tickets.db, "historical" = demo_dataset.db (read-only)
dataset_mode: str = "live"
