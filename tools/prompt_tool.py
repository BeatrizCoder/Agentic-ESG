"""Prompt management tool for template handling."""

from typing import Dict, Any, Optional
from . import BaseSupportTool


class PromptTool(BaseSupportTool):
    """Tool for managing prompt templates."""

    name: str = "Prompt Management Tool"
    description: str = "Loads and manages prompt templates"

    def __init__(self, prompt_service=None):
        super().__init__()
        self.prompt_service = prompt_service

    def _run(self, action: str, **kwargs) -> Dict[str, Any]:
        """Execute prompt operations."""
        if not self.prompt_service:
            return {"success": False, "error": "Prompt service not available"}

        if action == "get":
            return self._get_prompt(kwargs)
        elif action == "list":
            return self._list_prompts()
        else:
            return {"success": False, "error": f"Unknown action: {action}"}

    def _get_prompt(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Get a prompt template with variables injected."""
        try:
            prompt_name = data.get("name", "")
            variables = data.get("variables", {})
            prompt = self.prompt_service.get_prompt(prompt_name, variables)
            return {
                "success": True,
                "prompt": prompt,
                "template_used": prompt_name
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _list_prompts(self) -> Dict[str, Any]:
        """List available prompt templates."""
        try:
            prompts = self.prompt_service.list_available_prompts()
            return {"success": True, "prompts": prompts}
        except Exception as e:
            return {"success": False, "error": str(e)}