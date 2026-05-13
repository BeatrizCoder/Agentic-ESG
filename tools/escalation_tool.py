"""Escalation evaluation tool for support cases."""

from typing import Dict, Any
from . import BaseSupportTool


def _build_reference_id() -> str:
    import random
    return f"ESC-2026-{random.randint(1000, 9999)}"


class EscalationTool(BaseSupportTool):
    """Tool for evaluating if cases need escalation to human support."""

    name: str = "Escalation Evaluation Tool"
    description: str = "Evaluates if cases need escalation to human support"

    def __init__(self):
        super().__init__()

    def _run(self, response_confidence: int, sentiment: str, articles_count: int, inquiry: str) -> Dict[str, Any]:
        """Evaluate if case needs escalation."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import ESCALATION_KEYWORDS, ESCALATION_PHRASES, normalize_text
        import random

        escalate = False
        reason = "Sufficient confidence in automated response."
        triggered_keyword = None

        # Check for explicit escalation keywords in the inquiry (multilingual)
        normalized_inquiry = normalize_text(inquiry)

        # Combine all keywords from both languages
        all_keywords = ESCALATION_KEYWORDS["en"] + ESCALATION_KEYWORDS["pt"]

        for keyword in all_keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword in normalized_inquiry:
                escalate = True
                triggered_keyword = keyword
                reason = f"User explicitly requested escalation or human support (keyword: '{keyword}')."
                break

        # Check multi-word phrases
        if not escalate:
            for phrase in ESCALATION_PHRASES:
                normalized_phrase = normalize_text(phrase)
                if normalized_phrase in normalized_inquiry:
                    return {
                        "escalation_required": True,
                        "reason": f"Escalation phrase detected: '{phrase}'.",
                        "reference_id": _build_reference_id(),
                        "triggered_keyword": phrase,
                    }

        if not escalate:
            if response_confidence < 55:
                escalate = True
                reason = "Low confidence in automated response."
            elif sentiment == "Concerned" and response_confidence < 70:
                escalate = True
                reason = "Sensitive issue with low confidence."
            elif articles_count == 0:
                escalate = True
                reason = "Insufficient knowledge base support."

        reference_id = f"ESC-2026-{random.randint(1000, 9999)}" if escalate else ""

        return {
            "escalation_required": escalate,
            "reason": reason,
            "reference_id": reference_id,
            "triggered_keyword": triggered_keyword
        }