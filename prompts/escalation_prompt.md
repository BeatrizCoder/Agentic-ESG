# Escalation Prompt

Evaluate if this customer inquiry needs human escalation:

Inquiry: {inquiry}
Category: {category}
Sentiment: {sentiment}
Response Confidence: {response_confidence}

Escalate if:
- Customer explicitly requests human help
- Complex or sensitive issues
- Low confidence in automated response
- No relevant knowledge available

Return escalation decision with reason.