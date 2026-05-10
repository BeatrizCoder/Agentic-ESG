from __future__ import annotations

import json
import os
import random
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Iterable

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/api/support"
BACKEND_API_URL = os.environ.get("AAMAD_BACKEND_URL", DEFAULT_BACKEND_URL)

AGENTS = [
    {
        "name": "Classifier Agent",
        "emoji": "🔍",
        "task": "Analyzing request category...",
    },
    {
        "name": "Sentiment Analysis Agent",
        "emoji": "💭",
        "task": "Evaluating emotional tone...",
    },
    {
        "name": "Knowledge Retrieval Agent",
        "emoji": "📚",
        "task": "Searching knowledge base...",
    },
    {
        "name": "Response Generation Agent",
        "emoji": "✍️",
        "task": "Crafting response...",
    },
    {
        "name": "Escalation Agent",
        "emoji": "🚨",
        "task": "Evaluating escalation needs...",
    },
]

CATEGORY_KEYWORDS = {
    "Order Issues": ["order", "tracking", "shipment", "delivery", "package", "arrived", "delay"],
    "Billing": ["bill", "charge", "refund", "invoice", "payment", "price"],
    "Account Access": ["account", "login", "password", "sign in", "locked", "profile"],
    "Technical Issue": ["error", "bug", "crash", "failed", "site", "website", "problem"],
    "General Support": ["question", "help", "support", "information", "info", "request"],
}

KNOWLEDGE_BASE = {
    "Order Issues": [
        "Order Delivery Delays",
        "Tracking Your Package",
        "Order Status & Estimated Delivery",
    ],
    "Billing": [
        "Refunds and Billing Questions",
        "Understanding Your Invoice",
        "Payment Methods & Authorization Holds",
    ],
    "Account Access": [
        "Resetting Your Password",
        "Recovering a Locked Account",
        "Updating Account Information",
    ],
    "Technical Issue": [
        "Troubleshooting Login Errors",
        "Resolving Site Performance Problems",
        "Clearing Browser Cache",
    ],
    "General Support": [
        "Contacting Customer Service",
        "Using Our Help Center",
    ],
}

SENTIMENT_NEGATIVE = [
    "angry",
    "upset",
    "frustrated",
    "disappointed",
    "unhappy",
    "mad",
    "annoyed",
    "worried",
    "concerned",
    "not happy",
    "terrible",
]

SENTIMENT_URGENT = ["urgent", "asap", "immediately", "right away", "now"]

ESCALATION_KEYWORDS = {
    "en": [
        "escalate", "escalated", "talk to someone", "speak with someone",
        "human agent", "support agent", "manager", "supervisor",
        "refund", "reimbursement", "wrong order", "incorrect order",
        "damaged item", "complaint"
    ],
    "pt": [
        "reembolso", "quero reembolso", "nao recebi", "não recebi",
        "pedido errado", "veio errado", "falar com atendente",
        "suporte humano", "escalar", "escalada", "gerente", "supervisor",
        "reclamação", "reclamacao", "atendente humano", "falar com gerente"
    ]
}

def normalize_text(text: str) -> str:
    """Normalize text for keyword matching: lowercase, remove accents, trim."""
    # Convert to lowercase
    text = text.lower()
    # Remove accents
    text = unicodedata.normalize('NFD', text)
    text = ''.join(char for char in text if unicodedata.category(char) != 'Mn')
    # Trim whitespace
    return text.strip()

RESPONSE_TEMPLATES = {
    "Order Issues": (
        "I'm sorry to hear about the delay with your order. "
        "It looks like your shipment is experiencing a temporary delay, and it should arrive within the next 2-3 business days. "
        "If you'd like, I can provide more details on tracking and next steps."
    ),
    "Billing": (
        "I understand your concern about your billing statement. "
        "Our records show that the charge was processed correctly, but I can help review the payment details or initiate a refund request if needed."
    ),
    "Account Access": (
        "I can help you regain access to your account. "
        "Please try resetting your password from the sign-in page, and if the account is locked, I will escalate to our account recovery team."
    ),
    "Technical Issue": (
        "Thank you for letting us know about this technical issue. "
        "I recommend refreshing the page or clearing your browser cache, and if the problem persists, I can escalate it to our support engineers."
    ),
    "General Support": (
        "Thanks for reaching out. "
        "I can help answer your question or point you to the right support article so you can get a fast resolution."
    ),
}


@dataclass
class TicketResult:
    inquiry: str
    category: str
    category_confidence: int
    sentiment_label: str
    sentiment_confidence: int
    urgency: str
    articles: list[str]
    response: str
    response_confidence: int
    escalation_required: bool
    escalation_reason: str
    reference_id: str
    triggered_keyword: str | None = None


def normalize_text(text: str) -> str:
    return text.strip().lower()


def _count_matches(text: str, keywords: Iterable[str]) -> int:
    return sum(1 for token in keywords if token in text)


def detect_category(inquiry: str) -> tuple[str, int]:
    normalized = normalize_text(inquiry)
    scores = {}
    for category, keywords in CATEGORY_KEYWORDS.items():
        scores[category] = _count_matches(normalized, keywords)

    best = max(scores, key=scores.get)
    count = scores[best]
    confidence = min(95, 40 + count * 15)
    if best == "General Support" and count == 0:
        confidence = 50
    return best, confidence


def detect_sentiment(inquiry: str) -> tuple[str, int, str]:
    normalized = normalize_text(inquiry)
    found_negative = any(word in normalized for word in SENTIMENT_NEGATIVE)
    found_urgent = any(word in normalized for word in SENTIMENT_URGENT)
    if found_negative:
        label = "Concerned"
        confidence = 80
    elif found_urgent:
        label = "Urgent"
        confidence = 70
    else:
        label = "Neutral"
        confidence = 65

    if found_urgent:
        urgency = "High"
    elif found_negative:
        urgency = "Medium"
    else:
        urgency = "Low"
    return label, confidence, urgency


def retrieve_knowledge(category: str) -> list[str]:
    return KNOWLEDGE_BASE.get(category, KNOWLEDGE_BASE["General Support"])


def build_response(inquiry: str, category: str, sentiment: str, urgency: str, articles: list[str]) -> tuple[str, int]:
    base = RESPONSE_TEMPLATES.get(category, RESPONSE_TEMPLATES["General Support"])
    if urgency == "High":
        base += " I have flagged this as a priority, and our support team will respond as soon as possible."

    confidence = 60
    if category != "General Support":
        confidence += 15
    if sentiment == "Neutral":
        confidence += 5
    if len(articles) >= 2:
        confidence += 10
    confidence = min(95, confidence)

    return base, confidence


def evaluate_escalation(response_confidence: int, sentiment: str, articles: list[str], inquiry: str) -> tuple[bool, str, str, str | None]:
    # Check for explicit escalation keywords in the inquiry (multilingual)
    normalized_inquiry = normalize_text(inquiry)

    # Combine all keywords from both languages
    all_keywords = ESCALATION_KEYWORDS["en"] + ESCALATION_KEYWORDS["pt"]

    for keyword in all_keywords:
        normalized_keyword = normalize_text(keyword)
        if normalized_keyword in normalized_inquiry:
            return True, f"User explicitly requested escalation or human support (keyword: '{keyword}').", _build_reference_id(), keyword

    if response_confidence < 55:
        return True, "Low confidence in automated response.", _build_reference_id(), None
    if sentiment == "Concerned" and response_confidence < 70:
        return True, "Sensitive issue with low confidence.", _build_reference_id(), None
    if not articles or len(articles) < 1:
        return True, "Insufficient knowledge base support.", _build_reference_id(), None
    return False, "Sufficient confidence in automated response.", _build_reference_id(), None


def _build_reference_id() -> str:
    return "ESC-2026-" + str(random.randint(1000, 9999))


def analyze_ticket_remote(inquiry: str, backend_url: str) -> TicketResult:
    request_body = json.dumps({"inquiry": inquiry}).encode("utf-8")
    request = urllib.request.Request(
        backend_url,
        data=request_body,
        method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise ConnectionError(
            f"Falha ao conectar ao backend em {backend_url}: {exc}"
        )

    return TicketResult(
        inquiry=response_data.get("inquiry", inquiry),
        category=response_data["category"],
        category_confidence=response_data["category_confidence"],
        sentiment_label=response_data.get("sentiment", "Neutral"),
        sentiment_confidence=response_data["sentiment_confidence"],
        urgency=response_data["urgency"],
        articles=response_data["articles"],
        response=response_data["response"],
        response_confidence=response_data["response_confidence"],
        escalation_required=response_data["escalation_required"],
        escalation_reason=response_data["escalation_reason"],
        reference_id=response_data["reference_id"],
        triggered_keyword=response_data.get("triggered_keyword"),
    )


def analyze_ticket(inquiry: str, use_backend: bool = False, backend_url: str = BACKEND_API_URL) -> TicketResult:
    if use_backend:
        return analyze_ticket_remote(inquiry, backend_url)

    category, category_confidence = detect_category(inquiry)
    sentiment_label, sentiment_confidence, urgency = detect_sentiment(inquiry)
    articles = retrieve_knowledge(category)
    response, response_confidence = build_response(
        inquiry, category, sentiment_label, urgency, articles
    )
    escalation_required, escalation_reason, reference_id, triggered_keyword = evaluate_escalation(
        response_confidence, sentiment_label, articles, inquiry
    )
    return TicketResult(
        inquiry=inquiry,
        category=category,
        category_confidence=category_confidence,
        sentiment_label=sentiment_label,
        sentiment_confidence=sentiment_confidence,
        urgency=urgency,
        articles=articles,
        response=response,
        response_confidence=response_confidence,
        escalation_required=escalation_required,
        escalation_reason=escalation_reason,
        reference_id=reference_id,
        triggered_keyword=triggered_keyword,
    )


def print_header() -> None:
    print("\nMulti-Agent Customer Support Crew v1.0")
    print("=" * 40)


def print_agent_stage(index: int, result: TicketResult) -> None:
    agent = AGENTS[index]
    print(f"\nAgent {index + 1}/{len(AGENTS)}: {agent['name']} {agent['emoji']}")
    print(f"Status: {agent['task']}")
    time.sleep(0.6)

    if index == 0:
        print(f"✅ Completed: Category detected - \"{result.category}\"")
        print(f"Confidence: {result.category_confidence}%")
    elif index == 1:
        print(f"✅ Completed: Sentiment - \"{result.sentiment_label}\"")
        print(f"Urgency: {result.urgency}")
    elif index == 2:
        print(f"✅ Completed: Found {len(result.articles)} relevant article(s)")
        for title in result.articles[:3]:
            print(f"- \"{title}\"")
    elif index == 3:
        print("✅ Completed: Response generated")
        print(f"Confidence: {result.response_confidence}%")
    elif index == 4:
        if result.escalation_required:
            print("⚠️  ESCALATION TRIGGERED")
            print(f"Reason: {result.escalation_reason}")
        else:
            print("✅ Completed: No escalation needed")
            print(f"Reason: {result.escalation_reason}")


def print_final_result(result: TicketResult) -> None:
    print("\n" + "=" * 40)
    if result.escalation_required:
        print("🚨 HUMAN ESCALATION REQUIRED")
        print("=" * 40)
        print("\nYour inquiry has been flagged for human review due to its complexity. A support agent will contact you within 24 hours.")
        print(f"\nReference ID: {result.reference_id}")
        print("\nFor immediate assistance, please call 1-800-HELP-NOW.")
        print("\n[📞 Call Now] [📧 Email Update] [❌ New Inquiry]")
    else:
        print("📋 FINAL RESPONSE")
        print("=" * 40)
        print(f"\n{result.response}\n")
        print("[👍 Helpful] [👎 Not Helpful] [🔄 Retry] [📞 Escalate Manually] [❌ New Inquiry]")


def request_action() -> str:
    actions = {
        "1": "retry",
        "2": "retry_details",
        "3": "new",
        "4": "escalate",
        "5": "exit",
    }
    print("\nChoose an option:")
    print("1) Retry same inquiry")
    print("2) Retry with more details")
    print("3) New inquiry")
    print("4) Escalate manually")
    print("5) Exit")
    choice = input("> ").strip()
    return actions.get(choice, "new")


def sanitize_inquiry(inquiry: str) -> str:
    return inquiry.strip()


def run_loop(use_backend: bool = False, backend_url: str = BACKEND_API_URL) -> None:
    print_header()
    if use_backend:
        print(f"Backend integration enabled: {backend_url}")
    while True:
        inquiry = input("\nEnter your customer support inquiry (or type 'exit' to quit):\n> ").strip()
        if not inquiry:
            print("Please enter a non-empty inquiry.")
            continue
        if inquiry.lower() in {"exit", "quit"}:
            print("Goodbye!")
            return

        current_inquiry = sanitize_inquiry(inquiry)
        while True:
            try:
                result = analyze_ticket(current_inquiry, use_backend=use_backend, backend_url=backend_url)
            except ConnectionError as exc:
                print(f"\nErro: {exc}")
                if use_backend:
                    print("Voltando para o modo local.")
                    result = analyze_ticket(current_inquiry, use_backend=False)
                else:
                    raise
            print("\nProcessing your inquiry...")
            print("=" * 40)
            print("\n🤖 Starting Multi-Agent Analysis...")
            for stage in range(len(AGENTS)):
                print_agent_stage(stage, result)
            print_final_result(result)

            choice = request_action()
            if choice == "retry":
                continue
            if choice == "retry_details":
                extra = input("\nPlease provide additional details about your issue:\n> ").strip()
                if extra:
                    current_inquiry = f"{current_inquiry} {extra}"
                    continue
                print("No extra details provided. Re-running the original inquiry.")
                continue
            if choice == "escalate":
                print("\nManual escalation requested. Our human support team will review this inquiry.")
                break
            if choice == "new":
                break
            if choice == "exit":
                print("Goodbye!")
                return
        if choice == "exit":
            return


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Run the AAMAD frontend CLI. Use --backend to integrate with the FastAPI backend."
    )
    parser.add_argument(
        "--backend",
        action="store_true",
        help="Send inquiries to the backend API instead of running local logic.",
    )
    parser.add_argument(
        "--backend-url",
        default=BACKEND_API_URL,
        help=f"Backend support endpoint URL (default: {BACKEND_API_URL}).",
    )
    args = parser.parse_args(argv)

    try:
        run_loop(use_backend=args.backend, backend_url=args.backend_url)
        return 0
    except KeyboardInterrupt:
        print("\nInterrupted. Goodbye!")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
