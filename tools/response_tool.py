"""Response generation tool for customer support."""

from typing import Dict, Any
from . import BaseSupportTool
from .utils import clean_inquiry, detect_language


class ResponseTool(BaseSupportTool):
    """Tool for generating appropriate customer responses."""

    name: str = "Response Generation Tool"
    description: str = "Generates appropriate customer responses based on context"

    def __init__(self):
        super().__init__()

    def _run(self, category: str, urgency: str, article_count: int,
             inquiry: str = "", knowledge_context: str = "",
             routing_action: str = "resolve",
             external_context: str = "") -> Dict[str, Any]:
        """Generate response using LLM when USE_LLM=True, otherwise use templates."""
        import sys
        import os
        sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))
        from aamad.config import RESPONSE_TEMPLATES, USE_LLM, DEFAULT_MODEL

        if USE_LLM:
            try:
                from anthropic import Anthropic
                client = Anthropic()

                detected_lang  = detect_language(inquiry)
                clean_inq      = clean_inquiry(inquiry)
                lang_name      = "English" if detected_lang == 'en' else "Portuguese"
                lang_instruction = (
                    "MANDATORY: The customer wrote in ENGLISH. "
                    "You MUST respond in ENGLISH only. "
                    "Do NOT use Portuguese. Do NOT use Spanish. English only."
                    if detected_lang == 'en' else
                    "MANDATORY: O cliente escreveu em PORTUGUÊS. "
                    "Você DEVE responder em PORTUGUÊS apenas. "
                    "Não use inglês. Não use espanhol. Somente português."
                )

                knowledge_text = (
                    knowledge_context.strip()
                    if knowledge_context and knowledge_context.strip()
                    else "No specific articles available."
                )

                external_section = ""
                if external_context and external_context.strip():
                    external_section = (
                        f"IMPORTANT — Real-time data retrieved for this inquiry:\n"
                        f"{external_context}\n\n"
                        f"You MUST reference this real data in your response.\n"
                    )

                routing_block = ""
                if routing_action == "resolve":
                    routing_block = (
                        "\nThis is an INFORMATIONAL request. "
                        "The customer is asking for general information, NOT reporting a problem. "
                        "Answer directly and completely. "
                        "Do NOT ask for an order number. "
                        "Do NOT ask for more details.\n"
                    )
                elif routing_action == "step_by_step":
                    routing_block = (
                        "\nThis requires step-by-step guidance. "
                        "Provide clear numbered steps (1. 2. 3.). "
                        "Include relevant links as plain text if available. "
                        "End with an offer to help with any of the steps.\n"
                    )

                prompt = f"""{lang_instruction}

You are a helpful, empathetic customer support agent.

Customer inquiry: {clean_inq}
Language detected: {lang_name}
Category: {category}
Urgency: {urgency}

{external_section}Relevant knowledge base:
{knowledge_text}
{routing_block}
Instructions:
- {lang_instruction}
- Be warm and empathetic
- Answer the question directly — do NOT ask for more info if this is an informational or policy question
- Keep response under 150 words
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
                input_tokens  = result.usage.input_tokens
                output_tokens = result.usage.output_tokens
                real_cost = round(
                    (input_tokens * 0.0000008) + (output_tokens * 0.000004), 6
                )
                return {
                    "response": text,
                    "confidence": 90,
                    "template_used": "llm",
                    "execution_mode": "llm",
                    "knowledge_used": bool(knowledge_context and knowledge_context.strip()),
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
                    "detected_lang": detected_lang,
                }
            except Exception:
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
