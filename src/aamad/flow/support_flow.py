"""SupportFlow — CrewAI Flow orchestrating the full support pipeline."""

import os
import time
from typing import Any, Dict

import yaml
from crewai import Agent, Flow

from ..core import services as _svc
from ..config import ENABLE_MEMORY, DEFAULT_CONFIG
from .state import SupportState
from .steps import SupportFlowStepsMixin


class SupportFlow(SupportFlowStepsMixin, Flow[SupportState]):
    def __init__(self):
        super().__init__(tracing=True)
        self.steps: list[dict[str, Any]] = []
        self._start_time: float = time.time()
        self._cache_hit: bool = False
        self._inquiry_hash: str = ''
        # FlowMeta only scans the direct class namespace, missing mixin methods.
        # _flow_post_init (called above) populates self._methods from dir(self),
        # so we can now rebuild _start_methods and _listeners from it.
        self._register_mixin_methods()

    def _register_mixin_methods(self) -> None:
        """Re-register @start() / @listen() methods that FlowMeta missed (mixin origin)."""
        OR_CONDITION = "OR"
        # Work on fresh instance-level copies so we don't mutate class vars
        start_methods: list = list(self.__class__._start_methods)
        listeners: dict = dict(self.__class__._listeners)

        for method_name, method in self._methods.items():
            is_start = getattr(method, "__is_start_method__", False)
            trigger = getattr(method, "__trigger_methods__", None)
            trigger_cond = getattr(method, "__trigger_condition__", None)
            cond_type = getattr(method, "__condition_type__", OR_CONDITION) or OR_CONDITION

            if is_start and method_name not in start_methods:
                start_methods.append(method_name)

            if trigger and method_name not in listeners:
                if trigger_cond is not None:
                    listeners[method_name] = trigger_cond
                else:
                    listeners[method_name] = (cond_type, list(trigger))

        # Assign instance-level overrides so we don't pollute the class
        object.__setattr__(self, "_start_methods", start_methods)
        object.__setattr__(self, "_listeners", listeners)


# ── Legacy SupportCrew (non-Flow implementation, kept for reference) ──────────

def _load_yaml(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


class SupportCrew:
    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.steps: list[dict[str, Any]] = []
        self._create_agents()

    def _create_agents(self):
        from tools.classification_tool import ClassificationTool
        from tools.sentiment_tool import SentimentTool
        from tools.knowledge_tool import KnowledgeTool
        from tools.response_tool import ResponseTool
        from tools.escalation_tool import EscalationTool

        agents_config = _load_yaml("config/agents.yaml")
        for agent_name, config in agents_config.items():
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
                verbose=os.environ.get("CREWAI_VERBOSE", "false").lower() == "true",
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

    def ask_agent(
        self, from_agent: str, to_agent: str, question: str,
        context: dict[str, Any] | None = None,
    ) -> str:
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

    def delegate_task(
        self, from_agent: str, to_agent: str, task_description: str,
        context: dict[str, Any] | None = None,
    ) -> str:
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
        knowledge_result = self.execute_tool(
            "knowledge_agent", classification_result["category"], inquiry
        )

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

        if ENABLE_MEMORY:
            _svc.memory_service.store_interaction(
                inquiry=inquiry,
                category=classification_result["category"],
                sentiment=sentiment_result["sentiment"],
                escalation_required=escalation_result["escalation_required"],
                final_response=response_result["response"],
                reference_id=escalation_result.get("reference_id"),
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
