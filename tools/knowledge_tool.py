"""Knowledge retrieval tool for support categories."""

from . import BaseSupportTool


class KnowledgeTool(BaseSupportTool):
    """Tool for retrieving knowledge base articles."""

    name: str = "Knowledge Retrieval Tool"
    description: str = "Retrieves knowledge base articles for support categories"

    def __init__(self, knowledge_service=None):
        super().__init__()
        self.knowledge_service = knowledge_service

    def _run(self, category: str, inquiry: str = "") -> dict:
        if hasattr(self, 'knowledge_service') and self.knowledge_service:
            snippets = self.knowledge_service.get_snippets(category, inquiry)
            articles = [s["title"] for s in snippets]

            context_parts = []
            for s in snippets:
                context_parts.append(
                    f"[{s['source']}] {s['title']}:\n{s['content']}"
                )
            context_string = "\n\n---\n\n".join(context_parts)
            estimated_tokens = len(context_string) // 4

            return {
                "articles": articles,
                "snippets": snippets,
                "context_string": context_string,
                "count": len(articles),
                "source": "documents",
                "estimated_context_tokens": estimated_tokens,
                "sources_used": list(set(s["source"] for s in snippets))
            }

        return {
            "articles": [],
            "snippets": [],
            "context_string": "",
            "count": 0,
            "source": "none",
            "estimated_context_tokens": 0,
            "sources_used": []
        }