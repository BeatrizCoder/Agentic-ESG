"""CrewAI Task factories — one function per agent."""

from crewai import Task
from .definitions import (
    classification_agent,
    sentiment_agent,
    knowledge_agent,
    response_agent,
    summary_agent,
    quality_agent,
)


def make_classification_task(inquiry: str) -> Task:
    return Task(
        description=f"""
Classify this customer support inquiry and detect language.

Inquiry: {inquiry}

Return ONLY valid JSON:
{{
  "category": "Order Issues|Billing|Account Access|Technical Issue|General Support",
  "confidence": 0-100,
  "language": "pt|en",
  "language_confidence": 0-100,
  "scores": {{
    "Order Issues": 0-100,
    "Billing": 0-100,
    "Account Access": 0-100,
    "Technical Issue": 0-100,
    "General Support": 0-100
  }}
}}
""",
        expected_output="Valid JSON with category, confidence, language and scores",
        agent=classification_agent,
    )


def make_sentiment_task(inquiry: str) -> Task:
    return Task(
        description=f"""
Analyze the sentiment and urgency of this customer inquiry.

Inquiry: {inquiry}

Return ONLY valid JSON:
{{
  "sentiment": "Neutral|Concerned|Urgent",
  "urgency": "Low|Medium|High",
  "confidence": 0-100,
  "emotional_indicators": ["frustration", "confusion"]
}}
""",
        expected_output="Valid JSON with sentiment, urgency and confidence",
        agent=sentiment_agent,
    )


def make_knowledge_task(
    inquiry: str,
    category: str,
    knowledge_context: str,
) -> Task:
    return Task(
        description=f"""
You have retrieved these knowledge base snippets for a
customer support inquiry. Review them and identify the
most relevant information.

Category: {category}
Customer Inquiry: {inquiry}

Knowledge Base Snippets:
{knowledge_context}

Return a concise summary of the most relevant
knowledge points (max 300 words).
""",
        expected_output="Concise summary of relevant knowledge",
        agent=knowledge_agent,
    )


def make_response_task(
    inquiry: str,
    category: str,
    sentiment: str,
    urgency: str,
    routing_action: str,
    knowledge_summary: str,
    external_context: str,
    detected_language: str,
) -> Task:
    external_instructions = ""

    if "WEATHER DELAY ALERT" in external_context:
        external_instructions = """
WEATHER ALERT ACTIVE: Real weather data was retrieved.
Your response MUST mention the specific city,
real temperature and weather conditions.
Use appropriate weather emoji (🌧️ ⛈️ ☀️).
"""
    elif "WEATHER CHECK" in external_context:
        external_instructions = """
WEATHER CHECKED - NORMAL CONDITIONS.
Briefly mention weather was checked and is normal.
Explain that since weather is not the cause,
the team will investigate.
"""
    elif "LOGISTICS ALERT" in external_context:
        external_instructions = """
LOGISTICS ALERT ACTIVE: Fleet maintenance affecting deliveries.
Mention the validated address/city.
State +3 business days additional delay.
Use 🚛 emoji.
"""
    elif "REFUND DATA" in external_context:
        external_instructions = """
REFUND DATA RETRIEVED FROM DATABASE.
Mention exact order number, product name and amount.
Adapt tone to customer sentiment.
"""
    elif "PENDING ACTION FOUND" in external_context:
        external_instructions = """
EXISTING TICKET WITH PENDING ACTION FOUND.
Reference the existing ticket ID.
Clearly explain what action the customer needs to take.
"""

    return Task(
        description=f"""
Generate a helpful customer support response.

Customer Inquiry: {inquiry}
Category: {category}
Sentiment: {sentiment}
Urgency: {urgency}
Routing Action: {routing_action}
Customer Language: {detected_language}

Knowledge Base Summary:
{knowledge_summary or "No specific knowledge articles found."}

External Context (APIs/Database):
{external_context or "No external data retrieved."}

{external_instructions}

FORMATTING RULES:
- Respond in {detected_language.upper()} only
- Use appropriate emojis (1-3 max)
- Use line breaks between paragraphs
- Numbered steps each on own line
- Max 130 words
- Warm, professional tone
- Match urgency to customer's emotional state
""",
        expected_output=(
            f"A helpful support response in {detected_language}, "
            "properly formatted with emojis and line breaks"
        ),
        agent=response_agent,
    )


def make_summary_task(
    inquiry: str,
    category: str,
    sentiment: str,
    response: str,
) -> Task:
    return Task(
        description=f"""
Create a 2-line operator summary for this support ticket.

Customer Inquiry: {inquiry}
Category: {category}
Sentiment: {sentiment}
AI Response: {response}

Return ONLY valid JSON:
{{
  "summary": "One sentence describing the issue",
  "action_needed": "One sentence for operator action",
  "key_facts": ["fact1", "fact2", "fact3"]
}}
""",
        expected_output="Valid JSON with summary, action_needed and key_facts",
        agent=summary_agent,
    )


def make_quality_task(
    inquiry: str,
    response: str,
    category: str,
    knowledge_context: str,
    external_context: str,
) -> Task:
    return Task(
        description=f"""
Evaluate this AI-generated support response as an
independent quality judge. Be critical and objective.

Customer Inquiry: {inquiry}
AI Response to Evaluate: {response}
Category: {category}

Context available to the AI:
Knowledge: {knowledge_context[:300] if knowledge_context else "none"}
External data: {external_context[:300] if external_context else "none"}

Score each dimension 0-10:
1. FAITHFULNESS: Used real info or hallucinated?
2. RELEVANCE: Actually answered what was asked?
3. EMPATHY: Warm and appropriate tone?
4. COMPLETENESS: Enough info to help the customer?

Return ONLY valid JSON:
{{
  "faithfulness": 0-10,
  "relevance": 0-10,
  "empathy": 0-10,
  "completeness": 0-10,
  "overall": 0-10,
  "grade": "A|B|C|D|F",
  "hallucination_detected": true,
  "hallucination_details": "what was hallucinated or none",
  "issues": ["issue1"],
  "strengths": ["strength1"],
  "suggestion": "one improvement"
}}
""",
        expected_output="Valid JSON quality evaluation with scores and grade",
        agent=quality_agent,
    )
