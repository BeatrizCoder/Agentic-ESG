"""Classification tool for categorizing customer inquiries."""

from typing import Dict, Any
from . import BaseSupportTool
from .utils import clean_inquiry

VALID_CATEGORIES = ["Order Issues", "Billing", "Account Access", "Technical Issue", "General Support"]


class ClassificationTool(BaseSupportTool):
    """Tool for classifying customer inquiries into support categories."""

    name: str = "Classification Tool"
    description: str = "Classifies customer inquiries into appropriate support categories"

    def __init__(self):
        super().__init__()

    def _run(self, inquiry: str) -> Dict[str, Any]:
        """Classify inquiry using LLM when USE_LLM=True, otherwise keyword matching."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import CATEGORY_KEYWORDS, USE_LLM, DEFAULT_MODEL

        if USE_LLM:
            try:
                from anthropic import Anthropic
                client = Anthropic()
                clean_inq = clean_inquiry(inquiry)
                prompt = (
                    "You are a customer support classifier. Classify the following customer inquiry "
                    "into exactly ONE of these categories:\n"
                    "- Order Issues\n"
                    "- Billing\n"
                    "- Account Access\n"
                    "- Technical Issue\n"
                    "- General Support\n\n"
                    "Rules:\n"
                    "- Respond ONLY with a JSON object, no extra text.\n"
                    "- Format: {\"category\": \"<category name>\", \"confidence\": <0-100>}\n"
                    "- confidence reflects how certain you are (0=very uncertain, 100=very certain).\n"
                    "- Works for any language (Portuguese, English, etc.).\n\n"
                    "IMPORTANT DISTINCTIONS:\n\n"
                    "General Support (policy/information questions — no specific order):\n"
                    '- "What is your return policy?" → General Support\n'
                    '- "What is the refund policy?" → General Support\n'
                    '- "How do returns work?" → General Support\n'
                    '- "What is the exchange policy?" → General Support\n'
                    '- "How long do I have to return an item?" → General Support\n'
                    '- "Qual a política de devolução?" → General Support\n'
                    '- "Como funciona a devolução?" → General Support\n'
                    "These are INFORMATION requests, not problems with a specific order.\n\n"
                    "Order Issues (specific problems with a real order):\n"
                    '- "My order hasn\'t arrived" → Order Issues\n'
                    '- "I received the wrong item" → Order Issues\n'
                    '- "I want to return my order #12345" → Order Issues\n'
                    '- "Meu pedido não chegou" → Order Issues\n'
                    "These are specific problems that may need an order number.\n\n"
                    "Billing (financial issues — refunds, charges, payments):\n"
                    '- "I want a refund for order 11111" → Billing\n'
                    '- "Unauthorized charge on my card" → Billing\n'
                    '- "Quero reembolso" → Billing\n\n"'
                    f"Customer inquiry: \"{clean_inq}\""
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
                category = parsed.get("category", "General Support")
                if category not in VALID_CATEGORIES:
                    category = "General Support"
                confidence = int(parsed.get("confidence", 70))
                scores = {cat: (confidence if cat == category else 0) for cat in VALID_CATEGORIES}
                input_tokens = result.usage.input_tokens
                output_tokens = result.usage.output_tokens
                total_tokens = input_tokens + output_tokens
                cost_usd = round(
                    (input_tokens * 0.0000008) + (output_tokens * 0.000004), 6
                )
                return {
                    "category": category,
                    "confidence": confidence,
                    "scores": scores,
                    "execution_mode": "llm",
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": total_tokens,
                    "cost_usd": cost_usd,
                }
            except Exception:
                pass

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
            "scores": scores,
            "execution_mode": "deterministic",
        }
