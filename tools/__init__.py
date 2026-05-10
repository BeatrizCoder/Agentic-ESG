"""Base tool classes for the support system."""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from pydantic import BaseModel


class BaseSupportTool(ABC):
    """Base class for support tools, inspired by CrewAI BaseTool."""

    name: str
    description: str

    def __init__(self):
        pass

    @abstractmethod
    def _run(self, *args, **kwargs) -> Any:
        """Execute the tool with given arguments."""
        pass

    def run(self, *args, **kwargs) -> Any:
        """Public interface for tool execution."""
        return self._run(*args, **kwargs)

    async def _arun(self, *args, **kwargs) -> Any:
        """Async version for future use."""
        return self._run(*args, **kwargs)


class ToolResult(BaseModel):
    """Standardized tool execution result."""
    success: bool
    data: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None