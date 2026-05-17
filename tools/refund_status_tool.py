"""Refund status lookup tool — returns mock refund data by order number."""

import re
from typing import Dict, Any
from . import BaseSupportTool

_MOCK_REFUNDS: Dict[str, Dict[str, Any]] = {
    "11111": {
        "found": True,
        "auto_resolve": True,
        "should_escalate": False,
        "status": "approved_waiting_bank",
        "approval_date": "10/05/2025",
        "bank_deadline": "17/05/2025",
        "amount": "R$ 249,90",
        "can_auto_resolve": True,
        "message_pt": (
            "Seu reembolso do pedido 11111 foi aprovado em 10/05/2025. "
            "O valor de R$ 249,90 está sendo processado pelo banco e "
            "será creditado em sua conta até 17/05/2025. "
            "Esse prazo é definido pela instituição financeira e pode "
            "variar conforme a bandeira do cartão."
        ),
        "message_en": (
            "Your refund for order 11111 was approved on 05/10/2025. "
            "The amount of R$ 249.90 is being processed by the bank "
            "and will be credited to your account by 05/17/2025. "
            "This timeline is set by your financial institution."
        ),
    },
    "22222": {
        "found": True,
        "auto_resolve": True,
        "should_escalate": False,
        "status": "pending_analysis",
        "eta_days": 3,
        "can_auto_resolve": True,
        "message_pt": (
            "Seu pedido de reembolso do pedido 22222 está em análise "
            "pela nossa equipe financeira. A previsão de conclusão é "
            "de até 3 dias úteis. Assim que aprovado, você receberá "
            "uma confirmação por e-mail."
        ),
        "message_en": (
            "Your refund request for order 22222 is currently under "
            "review by our finance team. We expect to complete the "
            "analysis within 3 business days. Once approved, you will "
            "receive an email confirmation."
        ),
    },
    "33333": {
        "found": True,
        "auto_resolve": False,
        "should_escalate": True,
        "status": "denied",
        "can_auto_resolve": False,
        "message_pt": (
            "O reembolso do pedido 33333 foi negado. "
            "Um agente especializado entrará em contato para explicar "
            "os motivos da decisão e avaliar alternativas."
        ),
        "message_en": (
            "The refund for order 33333 was denied. "
            "A specialist agent will contact you to explain the "
            "decision and explore available alternatives."
        ),
    },
}

_ORDER_EXTRACT = re.compile(r'\b(\d{5,12})\b')
_REFUND_KEYWORDS = re.compile(
    r'reemb\w*|estorno|devolu[çc][aã]o|refund\w*|reimburs\w*'
    r'|dinheiro de volta|devolver o dinheiro|money back',
    re.IGNORECASE,
)


def is_refund_inquiry(text: str) -> bool:
    return bool(_REFUND_KEYWORDS.search(text))


def extract_order_number(text: str) -> str | None:
    m = re.search(r'pedido\s*[:#]?\s*(\d+)', text, re.IGNORECASE)
    if m:
        return m.group(1)
    m = _ORDER_EXTRACT.search(text)
    return m.group(1) if m else None


class RefundStatusTool(BaseSupportTool):
    name: str = "Refund Status Tool"
    description: str = "Looks up refund status for a given order number"

    def _run(self, order_number: str, language: str = "pt") -> Dict[str, Any]:
        data = _MOCK_REFUNDS.get(str(order_number))
        if not data:
            return {
                "found": False,
                "auto_resolve": False,
                "should_escalate": False,
                "status": "not_found",
                "can_auto_resolve": False,
                "order_number": order_number,
                "message_pt": (
                    f"Não encontramos informações de reembolso para o "
                    f"pedido {order_number}. Um agente verificará manualmente."
                ),
                "message_en": (
                    f"No refund information found for order {order_number}. "
                    "An agent will investigate manually."
                ),
            }
        return {**data, "order_number": order_number}
