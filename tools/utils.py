"""Shared utilities for support tools."""

import re


def clean_inquiry(inquiry: str) -> str:
    """Remove intake metadata appended to inquiry."""
    clean = inquiry
    clean = re.sub(r'\nEmail:\s*.+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\nName:\s*.+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\nPhone:\s*.+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r'\nCustomer Name:\s*.+', '', clean, flags=re.IGNORECASE)
    clean = re.sub(
        r'\n---\s*(?:Additional Information|Case Details)\s*---.*$',
        '', clean, flags=re.IGNORECASE | re.DOTALL
    )
    clean = re.sub(r'\[CUSTOMER REQUESTED.*?\]', '', clean, flags=re.IGNORECASE)
    clean = re.sub(r"',\)$", '', clean)
    return clean.strip()


def detect_language(text: str) -> str:
    """Return 'en' or 'pt'. English wins on a tie."""
    en_words = [
        'what', 'how', 'where', 'when', 'why', 'is',
        'the', 'your', 'my', 'order', 'return', 'policy',
        'refund', 'help', 'please', 'can', 'could', 'would',
        'have', 'has', 'not', 'arrived', 'want', 'need',
        'account', 'password', 'issue', 'problem', 'this',
        'locked', 'cannot', "can't",
    ]
    pt_words = [
        'meu', 'minha', 'não', 'nao', 'quero', 'preciso',
        'pedido', 'ajuda', 'problema', 'como', 'olá', 'ola',
        'obrigado', 'produto', 'conta', 'chegou', 'estou',
        'política', 'politica', 'devolução', 'devolucao',
        'qual', 'reembolso', 'estorno', 'fatura', 'prazo',
        'senha', 'esqueci', 'consigo',
    ]
    text_lower = text.lower()
    en_score = sum(1 for w in en_words if w in text_lower)
    pt_score = sum(1 for w in pt_words if w in text_lower)
    return 'pt' if pt_score > en_score else 'en'
