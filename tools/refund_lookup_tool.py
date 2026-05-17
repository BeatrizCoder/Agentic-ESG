"""Refund lookup tool with rich per-status message formatting."""

import re
from typing import Dict, Any
from . import BaseSupportTool

_MOCK_REFUNDS: Dict[str, Dict[str, Any]] = {
    "11111": {
        "found": True,
        "auto_resolve": True,
        "should_escalate": False,
        "status": "aprovado",
        "produto": "Tênis Running Pro",
        "valor": 150.00,
        "aprovado_em": "12/05/2025",
        "previsao": "17/05/2025",
        "can_auto_resolve": True,
    },
    "22222": {
        "found": True,
        "auto_resolve": True,
        "should_escalate": False,
        "status": "pendente",
        "produto": "Camiseta Esportiva",
        "valor": 89.90,
        "can_auto_resolve": True,
    },
    "33333": {
        "found": True,
        "auto_resolve": False,
        "should_escalate": True,
        "status": "negado",
        "produto": "Mochila Urbana",
        "valor": 199.00,
        "can_auto_resolve": False,
    },
    "44444": {
        "found": True,
        "auto_resolve": True,
        "should_escalate": False,
        "status": "processado",
        "produto": "Fone de Ouvido Bluetooth",
        "valor": 299.00,
        "can_auto_resolve": True,
    },
}

_REFUND_KEYWORDS = re.compile(
    r'reemb\w*|estorno|devolu[çc][aã]o|refund\w*|reimburs\w*'
    r'|dinheiro de volta|devolver o dinheiro|money back',
    re.IGNORECASE,
)

_ORDER_PATTERNS = [
    re.compile(r'pedido\s+(\d{4,8})', re.IGNORECASE),
    re.compile(r'reembolso\s+(\d{4,8})', re.IGNORECASE),
    re.compile(r'pedido\s*[:#]?\s*(\d{4,8})', re.IGNORECASE),
    re.compile(r'order\s*[:#]?\s*(\d{4,8})', re.IGNORECASE),
    re.compile(r'#(\d{4,8})'),
]


def _clean_inquiry(text: str) -> str:
    """Strip appended intake metadata before searching for order numbers."""
    clean = re.sub(r'\nPhone:.*', '', text, flags=re.IGNORECASE)
    clean = re.sub(r'\nEmail:.*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\nName:.*', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\n---.*$', '', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r"',\)$", '', clean)
    return clean.strip()


def is_refund_inquiry(text: str) -> bool:
    return bool(_REFUND_KEYWORDS.search(text))


def extract_order_number(text: str) -> str | None:
    clean = _clean_inquiry(text)
    for pattern in _ORDER_PATTERNS:
        m = pattern.search(clean)
        if m:
            return m.group(1)
    return None


def _format_status_pt(
    status: str, order: str, produto: str, valor: float,
    aprovado_em: str = "", previsao: str = "",
) -> str:
    if status == "processado":
        return (
            f"Boas notícias! O reembolso do pedido "
            f"#{order} ({produto}) no valor de "
            f"R${valor:.2f} já foi processado e o "
            f"valor foi devolvido para sua forma de "
            f"pagamento original. Caso não visualize "
            f"em seu extrato, aguarde até 2 dias úteis "
            f"para compensação bancária."
        )
    if status == "pendente":
        return (
            f"Sua solicitação de reembolso do pedido "
            f"#{order} ({produto}) no valor de "
            f"R${valor:.2f} está em análise pela nossa "
            f"equipe financeira. O prazo de análise é "
            f"de 3 a 5 dias úteis. Você receberá uma "
            f"confirmação por email assim que aprovado."
        )
    if status == "em_analise":
        return (
            f"Seu pedido de reembolso #{order} "
            f"({produto}) de R${valor:.2f} está sendo "
            f"analisado pela nossa equipe. Retornaremos "
            f"em até 2-3 dias úteis com uma decisão."
        )
    if status == "aprovado":
        return (
            f"Seu reembolso do pedido #{order} "
            f"({produto}) no valor de R${valor:.2f} "
            f"foi aprovado"
            f"{' em ' + aprovado_em if aprovado_em else ''}. "
            f"O valor será creditado na sua conta"
            f"{' até ' + previsao if previsao else ' em breve'}. "
            f"O prazo bancário pode levar até 5 dias "
            f"úteis após a aprovação."
        )
    if status == "negado":
        return (
            f"Infelizmente, o reembolso do pedido "
            f"#{order} ({produto}) no valor de "
            f"R${valor:.2f} foi negado. Um agente "
            f"especializado entrará em contato para "
            f"explicar os motivos da decisão e "
            f"avaliar alternativas."
        )
    return (
        f"Verificamos o pedido #{order} ({produto}). "
        f"Valor: R${valor:.2f}. Nossa equipe analisará sua solicitação."
    )


def _format_status_en(
    status: str, order: str, produto: str, valor: float,
    aprovado_em: str = "", previsao: str = "",
) -> str:
    if status == "processado":
        return (
            f"Great news! Your refund for order #{order} ({produto}) "
            f"of R${valor:.2f} has been processed and returned to your "
            f"original payment method. If not visible in your statement, "
            f"allow up to 2 business days for bank processing."
        )
    if status in ("pendente", "em_analise"):
        return (
            f"Your refund request for order #{order} ({produto}) "
            f"of R${valor:.2f} is under review by our finance team. "
            f"Expected resolution within 3-5 business days. "
            f"You will receive an email confirmation once approved."
        )
    if status == "aprovado":
        return (
            f"Your refund for order #{order} ({produto}) "
            f"of R${valor:.2f} has been approved"
            f"{' on ' + aprovado_em if aprovado_em else ''}. "
            f"Amount will be credited"
            f"{' by ' + previsao if previsao else ' soon'}. "
            f"Bank processing may take up to 5 business days."
        )
    if status == "negado":
        return (
            f"Unfortunately, the refund for order #{order} ({produto}) "
            f"of R${valor:.2f} was denied. A specialist will contact "
            f"you to explain the decision and explore alternatives."
        )
    return (
        f"We found your order #{order} ({produto}). "
        f"Amount: R${valor:.2f}. Our team will review your request."
    )


def _status_flags(status: str) -> tuple[bool, bool]:
    """Return (auto_resolve, should_escalate) for a given status string."""
    return (
        status in ("aprovado", "pendente", "processado", "em_analise"),
        status == "negado",
    )


class RefundLookupTool(BaseSupportTool):
    name: str = "Refund Status Tool"
    description: str = (
        "Looks up refund status for a given order number. "
        "Returns structured data with rich localised status messages."
    )

    def _run(self, order_number: str, language: str = "pt") -> Dict[str, Any]:
        import sys
        import os
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
        from aamad.data_store import data_store

        data = data_store.get_refund(str(order_number))

        # Fall back to in-memory mock when DB is unavailable or order not found
        if data is None:
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

        valor = float(data["valor"])
        produto = data["produto"]
        status = data["status"]
        aprovado_em = data.get("aprovado_em") or ""
        previsao = data.get("previsao_credito") or data.get("previsao") or ""

        auto_resolve, should_escalate = _status_flags(status)
        return {
            "found": True,
            "auto_resolve": auto_resolve,
            "should_escalate": should_escalate,
            "can_auto_resolve": auto_resolve,
            "status": status,
            "order_number": order_number,
            "produto": produto,
            "valor": valor,
            "aprovado_em": aprovado_em,
            "previsao_credito": previsao,
            "message_pt": _format_status_pt(
                status, order_number, produto, valor, aprovado_em, previsao
            ),
            "message_en": _format_status_en(
                status, order_number, produto, valor, aprovado_em, previsao
            ),
        }
