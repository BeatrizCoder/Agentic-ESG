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
        """Analyze sentiment using LLM when USE_LLM=True, otherwise keyword matching."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import SENTIMENT_NEGATIVE, SENTIMENT_URGENT, USE_LLM, DEFAULT_MODEL

        if USE_LLM:
            try:
                from anthropic import Anthropic
                client = Anthropic()
                prompt = (
                    "You are a sentiment analysis engine for customer support.\n"
                    "Analyze the following customer inquiry and return a JSON object.\n\n"
                    "Rules:\n"
                    "- sentiment must be exactly one of: \"Neutral\", \"Concerned\", \"Urgent\"\n"
                    "- urgency must be exactly one of: \"Low\", \"Medium\", \"High\"\n"
                    "- confidence is 0-100 (how certain you are of the sentiment).\n"
                    "- Respond ONLY with JSON, no extra text.\n"
                    "- Format: {\"sentiment\": \"<value>\", \"urgency\": \"<value>\", \"confidence\": <0-100>}\n"
                    "- Works for any language (Portuguese, English, etc.).\n\n"
                    "Guidelines:\n"
                    "- Urgent: customer uses words like 'urgente', 'immediately', 'asap', 'right now', 'agora'.\n"
                    "- Concerned: customer expresses frustration, worry, or dissatisfaction.\n"
                    "- Neutral: calm, informational tone.\n"
                    "- High urgency matches Urgent sentiment; Medium matches Concerned; Low matches Neutral.\n\n"
                    f"Customer inquiry: \"{inquiry}\""
                )
                result = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=60,
                    messages=[{"role": "user", "content": prompt}]
                )
                import json, re
                raw = result.content[0].text.strip()
                raw = re.sub(r"^```[a-z]*\n?", "", raw).rstrip("`").strip()
                parsed = json.loads(raw)
                sentiment = parsed.get("sentiment", "Neutral")
                urgency = parsed.get("urgency", "Low")
                confidence = int(parsed.get("confidence", 70))

                if sentiment not in ("Neutral", "Concerned", "Urgent"):
                    sentiment = "Neutral"
                if urgency not in ("Low", "Medium", "High"):
                    urgency = "Low"

                input_tokens = result.usage.input_tokens
                output_tokens = result.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                cost_usd = round(
                    (input_tokens * 0.0000008) + (output_tokens * 0.000004), 6
                )
                return {
                    "sentiment": sentiment,
                    "confidence": confidence,
                    "urgency": urgency,
                    "found_negative": sentiment == "Concerned",
                    "found_urgent": sentiment == "Urgent",
                    "execution_mode": "llm",
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                }
            except Exception:
                pass

        inquiry_lower = inquiry.lower()
        found_negative = any(term in inquiry_lower for term in SENTIMENT_NEGATIVE)
        found_urgent = any(term in inquiry_lower for term in SENTIMENT_URGENT)

        if found_negative:
            label, confidence = "Concerned", 80
        elif found_urgent:
            label, confidence = "Urgent", 70
        else:
            label, confidence = "Neutral", 65

        urgency = "High" if found_urgent else "Medium" if found_negative else "Low"

        return {
            "sentiment": label,
            "confidence": confidence,
            "urgency": urgency,
            "found_negative": found_negative,
            "found_urgent": found_urgent,
            "execution_mode": "deterministic",
        }
