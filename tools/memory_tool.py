"""Memory management tool for storing interactions."""

from typing import Dict, Any
from . import BaseSupportTool


class MemoryTool(BaseSupportTool):
    """Tool for managing conversation memory."""

    name: str = "Memory Management Tool"
    description: str = "Stores and retrieves conversation memory"

    def __init__(self, memory_service=None):
        super().__init__()
        self.memory_service = memory_service

    def _run(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute memory operations."""
        if not self.memory_service:
            return {"success": False, "error": "Memory service not available"}

        if action == "store":
            return self._store_interaction(kwargs)
        elif action == "retrieve":
            return self._retrieve_interactions(kwargs)
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    def _store_interaction(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Store an interaction in memory."""
        try:
            self.memory_service.store_interaction(
                inquiry=data.get("inquiry", ""),
                category=data.get("category", ""),
                sentiment=data.get("sentiment", ""),
                escalation_required=data.get("escalation_required", False),
                final_response=data.get("response", ""),
                reference_id=data.get("reference_id")
            )
            return {"success": True, "message": "Interaction stored"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _retrieve_interactions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Retrieve recent interactions."""
        try:
            limit = data.get("limit", 10)
            interactions = self.memory_service.get_recent_interactions(limit)
            return {"success": True, "interactions": interactions}
        except Exception as e:
            return {"success": False, "error": str(e)}