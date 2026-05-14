"""Response generation tool for customer support."""

from typing import Dict, Any
from . import BaseSupportTool


class ResponseTool(BaseSupportTool):
    """Tool for generating appropriate customer responses."""

    name: str = "Response Generation Tool"
    description: str = "Generates appropriate customer responses based on context"

    def __init__(self):
        super().__init__()

    @staticmethod
    def _is_portuguese(text: str) -> bool:
        pt_words = ['meu', 'minha', 'não', 'nao', 'quero', 'preciso',
                    'pedido', 'ajuda', 'problema', 'como', 'por', 'que',
                    'olá', 'ola', 'obrigado', 'produto', 'conta']
        text_lower = text.lower()
        return sum(1 for w in pt_words if w in text_lower) >= 2

    def _run(self, category: str, urgency: str, articles_count: int, inquiry: str = "") -> Dict[str, Any]:
        """Generate response using LLM when USE_LLM=True, otherwise use templates."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import RESPONSE_TEMPLATES, USE_LLM, DEFAULT_MODEL

        if USE_LLM:
            try:
                from anthropic import Anthropic
                client = Anthropic()
                detected_lang = "Portuguese (pt-BR)" if self._is_portuguese(inquiry) else "English"
                prompt = (
                    f"You are a friendly, empathetic customer support agent.\n\n"
                    f"IMPORTANT: Detected language: {detected_lang}. "
                    f"You MUST write your entire response in {detected_lang}. "
                    f"Never switch to a different language.\n\n"
                    f"Category: {category}\n"
                    f"Urgency: {urgency}\n"
                    f"Customer inquiry: {inquiry or '(not provided)'}\n\n"
                    f"Generate a helpful, empathetic response. Be concise and friendly. "
                    f"Do not mention internal categories or system details."
                )
                result = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=500,
                    messages=[{"role": "user", "content": prompt}]
                )
                import re
                text = result.content[0].text
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
                text = text.strip()
                # Capture real token usage and cost
                input_tokens = result.usage.input_tokens
                output_tokens = result.usage.output_tokens
                # claude-haiku-4-5: $0.80/M input, $4.00/M output
                real_cost = round(
                    (input_tokens * 0.0000008) + (output_tokens * 0.000004),
                    6
                )
                return {
                    "response": text,
                    "confidence": 90,
                    "template_used": "llm",
                    "execution_mode": "llm",
                    "token_usage": {
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "total_tokens": input_tokens + output_tokens,
                    },
                    "cost_usd": real_cost,
                }
            except Exception as e:
                # Fallback to template if LLM call fails
                pass

        template = RESPONSE_TEMPLATES.get(category, RESPONSE_TEMPLATES["General Support"])
        response = template
        if urgency == "High":
            response += " I have flagged this as a priority, and our support team will respond as soon as possible."

        confidence = 60
        if category != "General Support":
            confidence += 15
        if urgency == "Low":
            confidence += 5
        if articles_count >= 2:
            confidence += 10

        return {
            "response": response,
            "confidence": min(95, confidence),
            "template_used": category,
            "execution_mode": "deterministic",
        }
