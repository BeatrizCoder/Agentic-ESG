import re
import unicodedata
from dataclasses import dataclass
from typing import Optional


def normalize(text: str) -> str:
    text = text.lower().strip()
    text = unicodedata.normalize("NFD", text)
    return "".join(c for c in text if unicodedata.category(c) != "Mn")


ORDER_NUMBER_PATTERNS = [
    r'\b\d{5,12}\b',
    r'pedido\s*[:#]?\s*\d+',
    r'order\s*[:#]?\s*\d+',
    r'#\d{4,}',
]

EMAIL_PATTERNS = [
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
]

INVOICE_PATTERNS = [
    r'fatura\s*[:#]?\s*\d+',
    r'invoice\s*[:#]?\s*\d+',
    r'nota\s*fiscal\s*[:#]?\s*\d+',
    r'\b(nf|nfe)\s*[:#]?\s*\d+',
]

EXPLICIT_ESCALATION = [
    # PT
    "gerente", "supervisor", "responsavel", "responsável",
    "procon", "reclame aqui", "tribunal", "advogado",
    "processo", "absurdo", "inaceitavel", "inaceitável",
    "vou processar", "vou no procon", "quero meu dinheiro",
    "exijo", "indignado", "indignada", "revoltado",
    # EN
    "manager", "supervisor", "lawsuit", "lawyer", "attorney",
    "demand", "outrageous", "unacceptable", "worst service",
    "i demand", "legal action", "report you",
]

STEP_BY_STEP_CATEGORIES = ["Account Access", "Technical Issue"]
ALWAYS_ESCALATE_CATEGORIES = ["Billing"]

# HOW-TO patterns: informational questions that should resolve directly,
# never require order number or email.
HOW_TO_PATTERNS = [
    r'\bhow (do|can|to)\b',
    r'\bhow (do i|can i|should i)\b',
    r'\bwhat is (your|the)\b',
    r'\bwhat are (your|the)\b',
    r'\bwhere (do|can) i\b',
    r'\bcan you (explain|tell me|describe)\b',
    r'^como (fa[cç]o|posso|funciona|rastreio|rastrear)',
    r'\bcomo (fa[cç]o|posso|funciona|rastreio|rastrear)\b',
    r'\bqual [eé] (a|o)\b',
    r'\bquais s[aã]o\b',
    r'\bonde (posso|devo|fico)\b',
]


def _is_how_to_question(text: str) -> bool:
    """Returns True if the inquiry is an informational HOW-TO question."""
    norm = normalize(text)
    for pattern in HOW_TO_PATTERNS:
        if re.search(pattern, norm, re.IGNORECASE):
            return True
    return False


@dataclass
class RoutingDecision:
    action: str           # "escalate", "awaiting", "resolve", "step_by_step"
    reason: str
    missing_info: list[str]
    has_order_number: bool
    has_email: bool
    has_invoice: bool
    explicit_escalation: bool
    triggered_keyword: Optional[str]
    confidence: float     # 0-1


def _has_pattern(text: str, patterns: list[str]) -> bool:
    for p in patterns:
        if re.search(p, text, re.IGNORECASE):
            return True
    return False


def _find_explicit_escalation(text: str) -> Optional[str]:
    normalized = normalize(text)
    for kw in EXPLICIT_ESCALATION:
        if normalize(kw) in normalized:
            return kw
    return None


def route_ticket(
    inquiry: str,
    category: str,
    sentiment: str,
    urgency: str,
) -> RoutingDecision:
    norm_inquiry = normalize(inquiry)

    has_order   = _has_pattern(inquiry, ORDER_NUMBER_PATTERNS)
    has_email   = _has_pattern(inquiry, EMAIL_PATTERNS)
    has_invoice = _has_pattern(inquiry, INVOICE_PATTERNS)

    esc_keyword = _find_explicit_escalation(inquiry)

    missing = []

    # RULE 1: Explicit escalation always wins
    if esc_keyword:
        return RoutingDecision(
            action="escalate",
            reason=f"Customer explicitly requested escalation (keyword: '{esc_keyword}')",
            missing_info=[],
            has_order_number=has_order,
            has_email=has_email,
            has_invoice=has_invoice,
            explicit_escalation=True,
            triggered_keyword=esc_keyword,
            confidence=1.0,
        )

    # RULE 2: Billing always escalates
    if category == "Billing":
        return RoutingDecision(
            action="escalate",
            reason="Billing issues always require human review for financial security",
            missing_info=[],
            has_order_number=has_order,
            has_email=has_email,
            has_invoice=has_invoice,
            explicit_escalation=False,
            triggered_keyword=None,
            confidence=1.0,
        )

    # RULE 3a: HOW-TO questions resolve directly — never ask for order details
    if category == "Order Issues" and _is_how_to_question(inquiry):
        return RoutingDecision(
            action="resolve",
            reason="Informational HOW-TO question — no order details required",
            missing_info=[],
            has_order_number=has_order,
            has_email=has_email,
            has_invoice=has_invoice,
            explicit_escalation=False,
            triggered_keyword=None,
            confidence=0.85,
        )

    # RULE 3: Order Issues
    if category == "Order Issues":
        if not has_order:
            missing.append("order_number")
        if not has_email:
            missing.append("email")

        if missing:
            return RoutingDecision(
                action="awaiting",
                reason=f"Missing required information: {', '.join(missing)}",
                missing_info=missing,
                has_order_number=has_order,
                has_email=has_email,
                has_invoice=has_invoice,
                explicit_escalation=False,
                triggered_keyword=None,
                confidence=0.9,
            )
        else:
            return RoutingDecision(
                action="escalate",
                reason="Customer provided order details — routing to specialist for investigation",
                missing_info=[],
                has_order_number=has_order,
                has_email=has_email,
                has_invoice=has_invoice,
                explicit_escalation=False,
                triggered_keyword=None,
                confidence=0.95,
            )

    # RULE 4: Account Access → step by step
    if category == "Account Access":
        return RoutingDecision(
            action="step_by_step",
            reason="Account access issues can be resolved with guided instructions",
            missing_info=[],
            has_order_number=has_order,
            has_email=has_email,
            has_invoice=has_invoice,
            explicit_escalation=False,
            triggered_keyword=None,
            confidence=0.85,
        )

    # RULE 5: Technical Issue
    if category == "Technical Issue":
        has_screenshot = any(
            w in norm_inquiry
            for w in ["screenshot", "print", "foto", "imagem", "image"]
        )
        if not has_screenshot:
            missing.append("screenshot_or_description")

        if missing and urgency != "High":
            return RoutingDecision(
                action="awaiting",
                reason="Need more details to diagnose the issue",
                missing_info=missing,
                has_order_number=has_order,
                has_email=has_email,
                has_invoice=has_invoice,
                explicit_escalation=False,
                triggered_keyword=None,
                confidence=0.8,
            )
        else:
            return RoutingDecision(
                action="step_by_step",
                reason="Technical issue — providing troubleshooting steps",
                missing_info=[],
                has_order_number=has_order,
                has_email=has_email,
                has_invoice=has_invoice,
                explicit_escalation=False,
                triggered_keyword=None,
                confidence=0.85,
            )

    # RULE 6: General Support → auto-resolve
    return RoutingDecision(
        action="resolve",
        reason="General inquiry — AI can provide complete answer",
        missing_info=[],
        has_order_number=has_order,
        has_email=has_email,
        has_invoice=has_invoice,
        explicit_escalation=False,
        triggered_keyword=None,
        confidence=0.9,
    )
