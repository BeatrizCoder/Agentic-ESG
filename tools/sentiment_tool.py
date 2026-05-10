"""Sentiment analysis tool for customer inquiries."""

from typing import Dict, Any
from . import BaseSupportTool


class SentimentTool(BaseSupportTool):
    """Tool for analyzing sentiment and urgency in customer messages."""

    name: str = "Sentiment Analysis Tool"
    description: str = "Analyzes sentiment and urgency in customer messages"

    def __init__(self):
        super().__init__()

    def _run(self, inquiry: str) -> Dict[str, Any]:
        """Analyze sentiment using keyword matching."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import SENTIMENT_NEGATIVE, SENTIMENT_URGENT

        inquiry_lower = inquiry.lower()
        found_negative = any(term in inquiry_lower for term in SENTIMENT_NEGATIVE)
        found_urgent = any(term in inquiry_lower for term in SENTIMENT_URGENT)

        if found_negative:
            label = "Concerned"
            confidence = 80
        elif found_urgent:
            label = "Urgent"
            confidence = 70
        else:
            label = "Neutral"
            confidence = 65

        urgency = "High" if found_urgent else "Medium" if found_negative else "Low"

        return {
            "sentiment": label,
            "confidence": confidence,
            "urgency": urgency,
            "found_negative": found_negative,
            "found_urgent": found_urgent
        }