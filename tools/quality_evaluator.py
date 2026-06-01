"""LLM-as-a-judge quality evaluator: Sonnet judges Haiku responses."""

import anthropic
import json
import os
import time
import logging

logger = logging.getLogger(__name__)

JUDGE_MODEL = "claude-sonnet-4-6"
RESPONSE_MODEL = "claude-haiku-4-5"


class QualityEvaluator:
    """
    Cross-model quality evaluation.
    Sonnet (stronger) evaluates Haiku (faster) responses.
    Industry best practice for LLM quality assurance.
    """

    def __init__(self):
        self.client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY")
        )

    def evaluate(
        self,
        inquiry: str,
        response: str,
        category: str,
        routing_action: str,
        knowledge_context: str = "",
        external_context: str = "",
    ) -> dict:

        start_time = time.time()

        context_parts = []
        if knowledge_context:
            context_parts.append(
                f"Knowledge base snippets:\n{knowledge_context[:500]}"
            )
        if external_context:
            context_parts.append(
                f"External API data:\n{external_context[:300]}"
            )

        context_section = (
            "\n\n".join(context_parts)
            if context_parts
            else "No external context — response based on LLM knowledge only"
        )

        prompt = f"""You are an expert quality evaluator for an AI customer support system.

A support agent (claude-haiku-4-5) generated the response below.
Evaluate it critically and objectively as an independent judge.

---
CUSTOMER INQUIRY:
{inquiry}

AI RESPONSE TO EVALUATE:
{response}

CONTEXT AVAILABLE TO THE AI:
{context_section}

METADATA:
Category: {category}
Routing action: {routing_action}
---

Evaluate on these dimensions (0-10 scale):

1. FAITHFULNESS (0-10) — Hallucination detection
   Did the response stick to real information from the context,
   or did it invent/hallucinate facts?
   10 = everything stated is grounded in context or policy
   5  = some vague statements not clearly grounded
   0  = invented facts, wrong information, or contradictions

2. RELEVANCE (0-10)
   Did the response answer what the customer actually asked?
   10 = perfectly on-topic, directly helpful
   0  = completely missed the point

3. EMPATHY (0-10)
   Was the tone warm, professional, and appropriate
   for the customer's emotional state?
   10 = excellent tone, customer feels heard and valued
   0  = robotic, cold, dismissive, or inappropriate

4. COMPLETENESS (0-10)
   Did the response give enough information to actually help?
   10 = customer has everything they need to move forward
   0  = vague, incomplete, or missing critical information

5. HALLUCINATION_DETECTED (boolean)
   true = response contains at least one hallucinated fact
   false = no hallucinations detected

Grade scale:
A = overall >= 8.5
B = overall >= 7.0
C = overall >= 5.5
D = overall >= 4.0
F = overall < 4.0

Return ONLY valid JSON:
{{
  "faithfulness": <0-10>,
  "relevance": <0-10>,
  "empathy": <0-10>,
  "completeness": <0-10>,
  "overall": <weighted: faith*0.3 + rel*0.3 + emp*0.2 + comp*0.2>,
  "grade": "<A|B|C|D|F>",
  "hallucination_detected": <true|false>,
  "hallucination_details": "<what was hallucinated or 'none'>",
  "issues": ["<specific issue 1>", "<specific issue 2>"],
  "strengths": ["<strength 1>", "<strength 2>"],
  "suggestion": "<one actionable improvement>"
}}"""

        try:
            response_obj = self.client.messages.create(
                model=JUDGE_MODEL,
                max_tokens=500,
                messages=[{"role": "user", "content": prompt}]
            )

            text = response_obj.content[0].text.strip()
            text = text.replace("```json", "").replace("```", "").strip()
            result = json.loads(text)

            latency_ms = round((time.time() - start_time) * 1000, 2)

            # Sonnet pricing: Input $3/1M, Output $15/1M
            cost = round(
                (response_obj.usage.input_tokens * 0.000003) +
                (response_obj.usage.output_tokens * 0.000015),
                6
            )

            return {
                "evaluated": True,
                "judge_model": JUDGE_MODEL,
                "response_model": RESPONSE_MODEL,
                "faithfulness": result.get("faithfulness", 0),
                "relevance": result.get("relevance", 0),
                "empathy": result.get("empathy", 0),
                "completeness": result.get("completeness", 0),
                "overall": round(result.get("overall", 0), 1),
                "grade": result.get("grade", "N/A"),
                "hallucination_detected": result.get("hallucination_detected", False),
                "hallucination_details": result.get("hallucination_details", "none"),
                "issues": result.get("issues", []),
                "strengths": result.get("strengths", []),
                "suggestion": result.get("suggestion", ""),
                "input_tokens": response_obj.usage.input_tokens,
                "output_tokens": response_obj.usage.output_tokens,
                "cost_usd": cost,
                "latency_ms": latency_ms,
            }

        except Exception as e:
            logger.error("QualityEvaluator failed: %s", e)
            return {
                "evaluated": False,
                "error": str(e),
                "judge_model": JUDGE_MODEL,
                "hallucination_detected": None,
            }


quality_evaluator = QualityEvaluator()
