"""Knowledge retrieval tool for support categories."""

from typing import Dict, Any, Optional
from . import BaseSupportTool


class KnowledgeTool(BaseSupportTool):
    """Tool for retrieving knowledge base articles."""

    name: str = "Knowledge Retrieval Tool"
    description: str = "Retrieves knowledge base articles for support categories"

    def __init__(self, knowledge_service=None):
        super().__init__()
        self.knowledge_service = knowledge_service

    def _run(self, category: str, inquiry: Optional[str] = None) -> Dict[str, Any]:
        """Retrieve relevant articles for a category."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import ENABLE_CREWAI_KNOWLEDGE, KNOWLEDGE_BASE

        if ENABLE_CREWAI_KNOWLEDGE and inquiry and self.knowledge_service:
            # Use new knowledge service with search
            search_result = self.knowledge_service.search_knowledge(inquiry, category)
            return {
                "articles": search_result["articles"],
                "count": len(search_result["articles"]),
                "category": category,
                "source": search_result["source"],
                "snippets": search_result["snippets"]
            }
        else:
            # Fallback to hardcoded knowledge
            articles = KNOWLEDGE_BASE.get(category, KNOWLEDGE_BASE["General Support"])
            return {
                "articles": articles,
                "count": len(articles),
                "category": category,
                "source": "hardcoded"
            }