"""Unit tests for the AAMAD CLI frontend simulation."""

from __future__ import annotations

from aamad.frontend import analyze_ticket, detect_category, detect_sentiment


def test_detect_category_order_issue():
    category, confidence = detect_category("My order #12345 hasn't arrived yet.")
    assert category == "Order Issues"
    assert confidence >= 55


def test_detect_sentiment_concerned():
    label, confidence, urgency = detect_sentiment("I'm very upset that my package is late.")
    assert label == "Concerned"
    assert urgency == "Medium"
    assert confidence >= 70


def test_analyze_ticket_creates_response():
    result = analyze_ticket("I need help with a billing charge I don't recognize.")
    assert result.category == "Billing"
    assert "refund" in result.response.lower() or "billing" in result.response.lower()
    assert result.response_confidence >= 60
    assert result.reference_id.startswith("ESC-2026-")
