import logging
import time
import uuid
from datetime import datetime
from typing import Any
from dataclasses import dataclass, field, asdict
import json
import os
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ObservabilityEvent:
    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    reference_id: str = ""
    event_type: str = ""        # tool_start, tool_end, llm_call, escalation, error
    agent_name: str = ""
    tool_name: str = ""
    status: str = ""            # success, error, fallback, cached
    latency_ms: float = 0.0
    input_summary: str = ""
    output_summary: str = ""
    confidence: float = 0.0
    error: str = ""
    execution_mode: str = ""    # llm, deterministic
    cache_used: bool = False
    llm_used: bool = False
    knowledge_sources_used: list = field(default_factory=list)
    estimated_tokens: int = 0
    cost_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class ObservabilityService:
    def __init__(self):
        self.events: dict[str, list[ObservabilityEvent]] = {}
        self.data_dir = Path("src/aamad/data")
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.events_file = self.data_dir / "observability_events.json"
        self._load_events()

    def _load_events(self):
        """Load persisted events from disk."""
        try:
            if self.events_file.exists():
                data = json.loads(self.events_file.read_text())
                for ref_id, events_list in data.items():
                    self.events[ref_id] = [
                        ObservabilityEvent(**e) for e in events_list
                    ]
        except Exception:
            self.events = {}

    def _save_events(self):
        """Persist events to disk."""
        try:
            data = {
                ref_id: [e.to_dict() for e in events]
                for ref_id, events in self.events.items()
            }
            self.events_file.write_text(
                json.dumps(data, indent=2, ensure_ascii=False)
            )
        except Exception as e:
            logger.error("ObservabilityService: failed to save events: %s", e, exc_info=True)

    def record(self, event: ObservabilityEvent) -> None:
        """Record a single observability event."""
        if event.reference_id not in self.events:
            self.events[event.reference_id] = []
        self.events[event.reference_id].append(event)
        self._save_events()

    def record_tool_execution(
        self,
        reference_id: str,
        agent_name: str,
        tool_name: str,
        start_time: float,
        input_summary: str = "",
        output_summary: str = "",
        status: str = "success",
        confidence: float = 0.0,
        execution_mode: str = "deterministic",
        llm_used: bool = False,
        cache_used: bool = False,
        knowledge_sources: list = None,
        estimated_tokens: int = 0,
        cost_usd: float = 0.0,
        error: str = "",
        input_tokens: int = 0,
        output_tokens: int = 0,
        total_tokens: int = 0,
    ) -> ObservabilityEvent:
        latency_ms = round((time.time() - start_time) * 1000, 2)
        event = ObservabilityEvent(
            reference_id=reference_id,
            event_type="tool_execution",
            agent_name=agent_name,
            tool_name=tool_name,
            status=status,
            latency_ms=latency_ms,
            input_summary=input_summary[:200],
            output_summary=output_summary[:200],
            confidence=confidence,
            error=error,
            execution_mode=execution_mode,
            cache_used=cache_used,
            llm_used=llm_used,
            knowledge_sources_used=knowledge_sources or [],
            estimated_tokens=estimated_tokens,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=total_tokens,
        )
        self.record(event)
        return event

    def remap_events(self, old_key: str, new_key: str) -> None:
        """Move all events stored under old_key to new_key."""
        if old_key in self.events and old_key != new_key:
            self.events[new_key] = self.events.pop(old_key)
            self._save_events()

    def get_events(self, reference_id: str) -> list[dict]:
        """Get all events for a ticket."""
        return [
            e.to_dict()
            for e in self.events.get(reference_id, [])
        ]

    def get_summary(self) -> dict:
        """Aggregate metrics across all tickets."""
        all_events = [
            e for events in self.events.values()
            for e in events
        ]

        if not all_events:
            return {
                "total_events": 0,
                "total_tickets": 0,
                "avg_latency_ms": 0,
                "llm_calls": 0,
                "deterministic_calls": 0,
                "cache_hits": 0,
                "errors": 0,
                "total_estimated_tokens": 0,
                "total_cost_usd": 0.0,
                "agent_performance": {},
                "tool_usage": {},
            }

        agent_performance = {}
        tool_usage = {}

        for e in all_events:
            if e.agent_name:
                if e.agent_name not in agent_performance:
                    agent_performance[e.agent_name] = {
                        "calls": 0,
                        "total_latency_ms": 0,
                        "avg_latency_ms": 0,
                        "errors": 0,
                        "llm_calls": 0,
                        "avg_confidence": 0,
                        "total_confidence": 0,
                        "total_input_tokens": 0,
                        "total_output_tokens": 0,
                        "total_tokens": 0,
                        "total_cost_usd": 0.0,
                        "avg_tokens_per_call": 0,
                        "avg_cost_per_call": 0.0,
                    }
                ap = agent_performance[e.agent_name]
                ap["calls"] += 1
                ap["total_latency_ms"] += e.latency_ms
                ap["avg_latency_ms"] = round(
                    ap["total_latency_ms"] / ap["calls"], 2
                )
                if e.status == "error":
                    ap["errors"] += 1
                if e.llm_used:
                    ap["llm_calls"] += 1
                if e.confidence > 0:
                    ap["total_confidence"] += e.confidence
                    ap["avg_confidence"] = round(
                        ap["total_confidence"] / ap["calls"], 2
                    )
                ap["total_input_tokens"] += e.input_tokens
                ap["total_output_tokens"] += e.output_tokens
                ap["total_tokens"] += e.total_tokens
                ap["total_cost_usd"] = round(
                    ap["total_cost_usd"] + e.cost_usd, 6
                )
                ap["avg_tokens_per_call"] = round(
                    ap["total_tokens"] / ap["calls"], 1
                )
                ap["avg_cost_per_call"] = round(
                    ap["total_cost_usd"] / ap["calls"], 6
                )

            if e.tool_name:
                tool_usage[e.tool_name] = tool_usage.get(e.tool_name, 0) + 1

        llm_calls = sum(1 for e in all_events if e.llm_used)
        det_calls = sum(1 for e in all_events if not e.llm_used)

        return {
            "total_events": len(all_events),
            "total_tickets": len(self.events),
            "avg_latency_ms": round(
                sum(e.latency_ms for e in all_events) / len(all_events), 2
            ),
            "llm_calls": llm_calls,
            "deterministic_calls": det_calls,
            "cache_hits": sum(1 for e in all_events if e.cache_used),
            "errors": sum(1 for e in all_events if e.status == "error"),
            "total_estimated_tokens": sum(
                e.estimated_tokens for e in all_events
            ),
            "total_cost_usd": round(
                sum(e.cost_usd for e in all_events), 6
            ),
            "agent_performance": agent_performance,
            "tool_usage": tool_usage,
        }
