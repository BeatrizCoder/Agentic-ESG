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

    def _run(self, category: str, urgency: str, article_count: int,
             inquiry: str = "", knowledge_context: str = "",
             routing_action: str = "resolve") -> Dict[str, Any]:
        """Generate response using LLM when USE_LLM=True, otherwise use templates."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import RESPONSE_TEMPLATES, USE_LLM, DEFAULT_MODEL

        if USE_LLM:
            try:
                from anthropic import Anthropic
                client = Anthropic()
                has_knowledge = bool(knowledge_context and knowledge_context.strip())
                knowledge_section = (
                    f"Relevant knowledge base information:\n{knowledge_context}"
                    if has_knowledge
                    else "Use general knowledge."
                )

                is_direct_answer = (
                    routing_action == "resolve" or category == "General Support"
                )

                if routing_action == "step_by_step":
                    prompt = f"""You are a helpful customer support agent providing step-by-step guidance.

Customer inquiry: {inquiry}
Category: {category}

{knowledge_section}

Instructions for your response:
- Respond in the same language as the customer
- Provide clear numbered steps (1. 2. 3. etc.)
- Include the relevant links from the knowledge base as plain text URLs
- Be warm and reassuring
- Keep response under 200 words
- End with: "Let me know if you need help with any of these steps!" (PT: "Me diga se precisar de ajuda com algum desses passos!")
- Do not use markdown ** or # formatting
- Write links as plain text URLs"""
                else:
                    direct_answer_block = ""
                    if is_direct_answer:
                        direct_answer_block = """
IMPORTANT: This is a general information request.
The customer is asking a question, NOT reporting a problem.
You MUST answer the question directly and completely
using the knowledge base information provided.
Do NOT ask for more details.
Do NOT ask clarifying questions.
Just answer what was asked, clearly and completely.

Example:
- Customer asks 'What is your return policy?'
  → Answer: explain the return policy directly
- Customer asks 'How do I track my order?'
  → Answer: explain tracking steps directly
"""
                    prompt = f"""You are a helpful, empathetic customer support agent.

Customer inquiry: {inquiry}
Category: {category}
Urgency: {urgency}

{knowledge_section}
{direct_answer_block}
Instructions:
- Respond in the same language as the customer used
- If customer wrote in Portuguese, respond in Portuguese
- Be warm, empathetic and solution-focused
- Use the knowledge base information to give accurate answers
- Keep response concise — under 150 words
- Do not mention internal systems, agent names, or tools
- Do not use markdown formatting (no **, no #, no bullet hyphens)
- Write in plain conversational text"""
                result = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=400,
                    messages=[{"role": "user", "content": prompt}]
                )
                import re
                text = result.content[0].text
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
                text = text.strip()
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
                    "knowledge_used": has_knowledge,
                    "knowledge_sources": [],
                    "input_tokens": input_tokens,
                    "output_tokens": output_tokens,
                    "total_tokens": input_tokens + output_tokens,
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
        if article_count >= 2:
            confidence += 10

        return {
            "response": response,
            "confidence": min(95, confidence),
            "template_used": category,
            "execution_mode": "deterministic",
        }
