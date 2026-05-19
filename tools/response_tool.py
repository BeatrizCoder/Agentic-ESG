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

    def _format_response(self, text: str) -> str:
        """Post-process LLM response to ensure proper formatting and line breaks."""
        import re
        # Ensure numbered steps that run together get separated
        # "1. Step one 2. Step two" → "1. Step one\n2. Step two"
        text = re.sub(r'(\d+\.\s+[^\d]+?)(?=\d+\.)', r'\1\n', text)
        # Remove excessive blank lines (max 2 consecutive)
        text = re.sub(r'\n{3,}', '\n\n', text)
        # Ensure a blank line before a numbered list that follows a sentence
        text = re.sub(r'([.!?:])\s+(1\.)', r'\1\n\n\2', text)
        return text.strip()

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

                alert_instructions = ""
                if "LOGISTICS ALERT ACTIVE" in (external_context or ""):
                    alert_instructions = (
                        "\nIMPORTANT: There is an active logistics alert for the customer's region. "
                        "Your response MUST:\n"
                        "- Acknowledge the specific validated address from the data above\n"
                        "- Mention the fleet maintenance situation causing the delay\n"
                        "- State the 3 additional business days delay clearly\n"
                        "- Be empathetic and apologetic\n"
                        "- Do NOT ask for more information — resolve this directly\n"
                    )
                elif "WEATHER DELAY ALERT" in (external_context or ""):
                    alert_instructions = (
                        "\nSITUATION: Adverse weather affecting deliveries "
                        "in the customer's region. Real weather data retrieved.\n"
                        "Your response MUST:\n"
                        "- Start with weather emoji (🌧️ 🌩️ ⛈️ based on conditions)\n"
                        "- Mention the specific city and real temperature\n"
                        "- Mention the real weather conditions\n"
                        "- Explain weather is causing delivery delays\n"
                        "- Estimate 1-2 additional business days\n"
                        "- Be warm and reassuring\n"
                        "- Under 100 words\n"
                        "- Do NOT ask for more information — resolve this directly\n"
                    )

                elif "CLEAR WEATHER ESCALATION" in (external_context or ""):
                    alert_instructions = (
                        "\nSITUATION: Weather is normal, order being escalated.\n"
                        "Your response MUST:\n"
                        "- Start with ☀️ emoji\n"
                        "- Briefly mention weather was checked and is normal\n"
                        "- Mention the city name and conditions from the data\n"
                        "- Explain that since weather is not the cause, "
                        "the team will investigate directly\n"
                        "- Sound reassuring and professional\n"
                        "- Under 80 words\n"
                    )

                elif ("WEATHER CHECK" in (external_context or "") and
                      ("normal conditions" in (external_context or "") or
                       "No weather impact" in (external_context or ""))):
                    alert_instructions = (
                        "\nSITUATION: Weather was checked but conditions are NORMAL. "
                        "No weather-related delivery issues in the customer's region.\n"
                        "Your response MUST:\n"
                        "- Start with ☀️ emoji\n"
                        "- Briefly mention weather was checked and is normal\n"
                        "- Explain that since weather is not the cause, "
                        "the team will investigate the order directly\n"
                        "- Be reassuring and professional\n"
                        "- Mention the order number if provided\n"
                        "- Keep under 80 words\n"
                        "- Respond in customer's language\n"
                    )

                elif "REFUND DATA FOUND" in (external_context or ""):
                    alert_instructions = (
                        "\nSITUATION: Refund record found in database. "
                        "The customer is asking about their refund status. "
                        "Use the exact data provided in the real-time data above.\n"
                        "Your response MUST:\n"
                        "- Address the customer's specific concern empathetically\n"
                        "- Mention the EXACT order number\n"
                        "- Mention the EXACT product name if available\n"
                        "- Mention the EXACT amount in R$ if available\n"
                        "- Clearly explain the current status in plain language\n"
                        "- If approved but bank not processed: explain banking timeline\n"
                        "- If processed: confirm money was returned\n"
                        "- If pending: give realistic timeline\n"
                        "- Match the tone to customer sentiment "
                        "(if frustrated: more apologetic, if neutral: informative)\n"
                        "- Keep under 120 words\n"
                        "- Sound human, not like a template\n"
                        "- Do NOT ask for more information — resolve this directly\n"
                    )

                elif "PENDING ACTION FOUND" in (external_context or ""):
                    is_photo    = "AWAITING_PHOTO"            in (external_context or "")
                    is_label    = "LABEL_EXPIRED"             in (external_context or "")
                    is_ship     = "AWAITING_RETURN_SHIPMENT"  in (external_context or "")
                    is_docs     = "AWAITING_DOCUMENTATION"    in (external_context or "")
                    is_delivery = "DELIVERY_FAILED"           in (external_context or "")
                    is_warranty = "UNDER_TECHNICAL_ANALYSIS"  in (external_context or "")
                    is_return   = "AWAITING_RETURN"           in (external_context or "")

                    if is_photo:
                        emoji = "📸"
                        situation = "product arrived damaged, waiting for photo"
                    elif is_label:
                        emoji = "📦"
                        situation = "return label expired, needs new label"
                    elif is_ship:
                        emoji = "🚚"
                        situation = "exchange approved, waiting for customer to ship product back"
                    elif is_docs:
                        emoji = "📄"
                        situation = "billing dispute open, waiting for payment proof"
                    elif is_delivery:
                        emoji = "🏠"
                        situation = "delivery failed twice, needs rescheduling"
                    elif is_warranty:
                        emoji = "🔧"
                        situation = "product under technical analysis at service center"
                    elif is_return:
                        emoji = "↩️"
                        situation = "cancellation approved, waiting for product return"
                    else:
                        emoji = "⏳"
                        situation = "pending action required"

                    alert_instructions = f"""
SITUATION: {situation}
The customer has an EXISTING open ticket that requires action.
Emoji: {emoji}

Your response MUST:
- Start with {emoji} emoji
- Reference the existing ticket ID from the data
- Mention the EXACT product name and value
- Clearly explain what action the customer needs to take
- Mention the deadline if urgent
- If deadline has passed: acknowledge urgency
- Provide specific next steps
- Be empathetic but clear and actionable
- Include any URLs or instructions from additional_info (Details)
- Keep under 150 words
- Respond in customer's language

Do NOT suggest escalation — the ticket already exists.
Do NOT ask for information already in the system.
Focus on what the CUSTOMER needs to DO next.
"""

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
                        "Format EXACTLY like this:\n\n"
                        "[Brief empathetic intro — 1 sentence]\n\n"
                        "[numbered steps, each on its own line]\n"
                        "1. First action\n"
                        "2. Second action\n"
                        "3. Third action\n\n"
                        "[Closing line offering more help]\n\n"
                        "Each numbered step MUST be on its own line. "
                        "Include relevant links as plain text if available.\n"
                    )

                dynamic_prompt = f"""{lang_instruction}

Customer inquiry: {clean_inq}
Language detected: {lang_name}
Category: {category}
Urgency: {urgency}

{external_section}{routing_block}{alert_instructions}
Instructions:
- {lang_instruction}
- Be warm and empathetic
- Answer the question directly — do NOT ask for more info if this is an informational or policy question
- Keep response under 150 words
- Do not mention internal systems, agent names, or tools

Formatting rules (MANDATORY):
- Use line breaks between paragraphs (\\n\\n)
- When listing steps, put EACH step on its own line:
  1. First step
  2. Second step
  3. Third step
- Separate action items from the explanation with a blank line
- Keep each paragraph focused on ONE idea
- Maximum 3 paragraphs total
- Do NOT use markdown (no **, no #, no ---)
- Do NOT use bullet points with hyphens (-)
- Use numbered lists (1. 2. 3.) for steps only
- Each numbered step must be on its own line
- Add a blank line before and after numbered lists

Example of CORRECT format:
"Entendo sua situação e vou ajudá-lo.

Seu reembolso foi aprovado em 10/05. O banco pode levar até 5 dias úteis para processar.

Para verificar:
1. Acesse seu extrato bancário
2. Procure por crédito nos últimos 5 dias
3. Se não encontrar, entre em contato conosco

Estamos à disposição para ajudar!"

Example of WRONG format (do not do this):
"Seu reembolso foi aprovado. O banco leva 5 dias. Para verificar: 1. Acesse seu extrato 2. Procure o crédito Se não encontrar, entre em contato." """

                result = client.messages.create(
                    model=DEFAULT_MODEL,
                    max_tokens=400,
                    system=[
                        {
                            "type": "text",
                            "text": "You are a helpful, empathetic customer support agent.",
                            "cache_control": {"type": "ephemeral"}
                        }
                    ],
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": f"Relevant knowledge base:\n{knowledge_text}",
                                    "cache_control": {"type": "ephemeral"}
                                },
                                {
                                    "type": "text",
                                    "text": dynamic_prompt
                                }
                            ]
                        }
                    ]
                )
                import re
                text = result.content[0].text
                text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
                text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
                text = text.strip()
                text = self._format_response(text)
                input_tokens  = result.usage.input_tokens
                output_tokens = result.usage.output_tokens
                cache_create = getattr(result.usage, 'cache_creation_input_tokens', 0) or 0
                cache_read = getattr(result.usage, 'cache_read_input_tokens', 0) or 0
                real_cost = round(
                    (input_tokens * 0.0000008) +
                    (cache_create * 0.000001) +
                    (cache_read * 0.00000008) +
                    (output_tokens * 0.000004),
                    6
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
