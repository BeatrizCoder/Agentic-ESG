"""Classification tool for categorizing customer inquiries."""

from typing import Dict, Any
from . import BaseSupportTool


class ClassificationTool(BaseSupportTool):
    """Tool for classifying customer inquiries into support categories."""

    name: str = "Classification Tool"
    description: str = "Classifies customer inquiries into appropriate support categories"

    def __init__(self):
        super().__init__()

    def _run(self, inquiry: str) -> Dict[str, Any]:
        """Classify inquiry using keyword matching."""
        # Import here to avoid circular imports
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import CATEGORY_KEYWORDS

        inquiry_lower = inquiry.lower()
        scores = {cat: sum(word in inquiry_lower for word in keywords)
                 for cat, keywords in CATEGORY_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        count = scores[best]
        confidence = min(95, 40 + count * 15)
        if best == "General Support" and count == 0:
            confidence = 55

        return {
            "category": best,
            "confidence": confidence,
            "scores": scores
        }