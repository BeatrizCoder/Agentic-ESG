"""Tool registry and execution governance for the support system."""

import time
from typing import Dict, Any, List
import logging

logger = logging.getLogger(__name__)


class ToolRegistry:
    """Registry for managing and executing tools."""

    def __init__(self):
        self.tools: Dict[str, Any] = {}
        self.allowlist: List[str] = []
        self.blocklist: List[str] = []
        self.cache: Dict[str, Any] = {}
        self.cache_enabled = True

    def register_tool(self, tool_class: Any, name: str = None) -> None:
        """Register a tool in the registry."""
        tool_name = name or tool_class.name
        self.tools[tool_name] = tool_class()
        logger.info(f"Registered tool: {tool_name}")

    def execute_tool(self, tool_name: str, *args, **kwargs) -> Dict[str, Any]:
        """Execute a tool with governance and caching."""
        start_time = time.time()

        # Check allowlist/blocklist
        if self.allowlist and tool_name not in self.allowlist:
            return self._create_error_result(f"Tool {tool_name} not in allowlist")
        if tool_name in self.blocklist:
            return self._create_error_result(f"Tool {tool_name} is blocked")

        # Check cache
        cache_key = self._generate_cache_key(tool_name, args, kwargs)
        if self.cache_enabled and cache_key in self.cache:
            logger.info(f"Cache hit for tool: {tool_name}")
            result = self.cache[cache_key]
            result["cached"] = True
            return result

        # Execute tool
        try:
            tool = self.tools.get(tool_name)
            if not tool:
                return self._create_error_result(f"Tool {tool_name} not found")

            result = tool._run(*args, **kwargs)
            execution_time = time.time() - start_time

            # Add metadata
            result.update({
                "tool_name": tool_name,
                "execution_time": execution_time,
                "cached": False,
                "success": True
            })

            # Cache result if appropriate
            if self._should_cache(tool_name, result):
                self.cache[cache_key] = result

            logger.info(f"Executed tool {tool_name} in {execution_time:.3f}s")
            return result

        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Tool {tool_name} failed after {execution_time:.3f}s: {str(e)}")
            return self._create_error_result(f"Tool execution failed: {str(e)}")

    def _generate_cache_key(self, tool_name: str, args: tuple, kwargs: dict) -> str:
        """Generate a cache key for tool execution."""
        # Simple cache key - in production, use proper hashing
        key_parts = [tool_name] + list(args) + [f"{k}={v}" for k, v in sorted(kwargs.items())]
        return "|".join(str(part) for part in key_parts)

    def _should_cache(self, tool_name: str, result: Dict[str, Any]) -> bool:
        """Determine if result should be cached."""
        # Cache classification, sentiment, and knowledge results
        cacheable_tools = ["Classification Tool", "Sentiment Analysis Tool", "Knowledge Retrieval Tool"]
        return tool_name in cacheable_tools and result.get("success", True)

    def _create_error_result(self, message: str) -> Dict[str, Any]:
        """Create a standardized error result."""
        return {
            "success": False,
            "error": message,
            "cached": False,
            "execution_time": 0
        }

    def list_tools(self) -> List[str]:
        """List all registered tools."""
        return list(self.tools.keys())

    def clear_cache(self) -> None:
        """Clear the tool execution cache."""
        self.cache.clear()
        logger.info("Tool cache cleared")

    def set_allowlist(self, tools: List[str]) -> None:
        """Set the tool allowlist."""
        self.allowlist = tools

    def set_blocklist(self, tools: List[str]) -> None:
        """Set the tool blocklist."""
        self.blocklist = tools