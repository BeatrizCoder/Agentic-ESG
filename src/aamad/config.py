"""Configuration module for AAMAD backend features."""

import os
import unicodedata
from typing import Dict, Any, List

# Feature flags
USE_LLM: bool = True
DEFAULT_MODEL: str = "claude-haiku-4-5-20251001"
ENABLE_MEMORY: bool = os.getenv("ENABLE_MEMORY", "false").lower() == "true"
ENABLE_CREWAI_KNOWLEDGE: bool = os.getenv("ENABLE_CREWAI_KNOWLEDGE", "false").lower() == "true"
ENABLE_PROMPT_TEMPLATES: bool = os.getenv("ENABLE_PROMPT_TEMPLATES", "true").lower() == "true"
ENABLE_MCP: bool = os.getenv("ENABLE_MCP", "false").lower() == "true"
ENABLE_EXTERNAL_APIS: bool = os.getenv("ENABLE_EXTERNAL_APIS", "true").lower() == "true"
ENABLE_MOCK_INTEGRATIONS: bool = os.getenv("ENABLE_MOCK_INTEGRATIONS", "true").lower() == "true"
ENABLE_REDIS_CACHE: bool = os.getenv("ENABLE_REDIS_CACHE", "false").lower() == "true"

# Database configuration
DATABASE_PROVIDER: str = os.getenv("DATABASE_PROVIDER", "sqlite")  # sqlite or postgres
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///src/aamad/data/tickets.db")

# SQLAlchemy requires "postgresql://" — Heroku/Neon may return "postgres://"
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Redis configuration
REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

# External API authentication
EXTERNAL_API_KEY: str = os.getenv("EXTERNAL_API_KEY", "")
GITHUB_TOKEN: str = os.getenv("GITHUB_TOKEN", "")
WEATHER_API_KEY: str = os.getenv("WEATHER_API_KEY", "")
OAUTH_CLIENT_ID: str = os.getenv("OAUTH_CLIENT_ID", "")
OAUTH_CLIENT_SECRET: str = os.getenv("OAUTH_CLIENT_SECRET", "")

# Integration configuration
INTEGRATION_CONFIG = {
    "retry_count": int(os.getenv("INTEGRATION_RETRY_COUNT", "3")),
    "timeout_seconds": int(os.getenv("INTEGRATION_TIMEOUT_SECONDS", "30")),
    "rate_limit_per_minute": int(os.getenv("INTEGRATION_RATE_LIMIT_PER_MINUTE", "60")),
}

# Paths
KNOWLEDGE_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "knowledge")
PROMPTS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "prompts")
MEMORY_FILE: str = os.path.join(os.path.dirname(__file__), "..", "..", "memory.json")
SKILLS_DIR: str = os.path.join(os.path.dirname(__file__), "..", "..", "skills")

# Tool constants
CATEGORY_KEYWORDS = {
    "Order Issues": ["order", "tracking", "shipment", "delivery", "package", "arrived", "delay"],
    "Billing": ["bill", "charge", "refund", "invoice", "payment", "price",
                "reembolso", "estorno", "fatura", "cobrança", "cobranca"],
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
    "angry", "upset", "frustrated", "disappointed", "unhappy", "mad", "annoyed",
    "worried", "concerned", "not happy", "terrible",
]

SENTIMENT_URGENT = ["urgent", "asap", "immediately", "right away", "now"]

ESCALATION_KEYWORDS = {
    "en": [
        "escalate", "escalated", "talk to someone", "speak with someone",
        "speak to someone", "human agent", "support agent", "live agent",
        "real person", "real agent", "manager", "supervisor", "team lead",
        "refund", "reimbursement", "money back", "charge back", "chargeback",
        "dispute", "unauthorized charge", "wrong charge", "overcharged",
        "wrong order", "incorrect order", "missing order", "never arrived",
        "damaged item", "broken item", "defective", "not working",
        "never received", "where is my order", "lost package",
        "account hacked", "unauthorized access", "data breach", "lawsuit",
        "legal action", "lawyer", "attorney", "report", "fraud",
        "unacceptable", "ridiculous", "terrible service", "worst experience",
        "completely useless", "incompetent", "furious", "outraged",
        "cancel account", "cancel subscription", "close account",
        "delete account", "terminate",
        "complaint", "file a complaint", "formal complaint",
    ],
    "pt": [
        "falar com atendente", "falar com alguem", "falar com alguém",
        "quero atendente", "quero humano", "atendente humano",
        "falar com gerente", "falar com supervisor", "pessoa real",
        "escalar", "escalada", "gerente", "supervisor", "responsavel",
        "responsável",
        "reembolso", "reemb", "quero meu dinheiro", "dinheiro de volta",
        "estornar", "estorno", "cobrado errado", "cobrança indevida",
        "cobrança errada", "cobrança duplicada", "me cobraram",
        "pagamento errado", "não autorizei", "nao autorizei",
        "pedido errado", "veio errado", "produto errado", "item errado",
        "nao recebi", "não recebi", "nunca chegou", "cadê meu pedido",
        "cade meu pedido", "sumiu", "perdido", "extraviado",
        "produto danificado", "chegou quebrado", "chegou com defeito",
        "com defeito", "nao funciona", "não funciona", "defeituoso",
        "conta hackeada", "acesso nao autorizado", "acesso não autorizado",
        "fraude", "golpe", "processo", "advogado", "procon",
        "reclame aqui", "tribunal",
        "inaceitavel", "inaceitável", "absurdo", "ridiculo", "ridículo",
        "pessimo", "péssimo", "horrivel", "horrível", "vergonhoso",
        "incompetente", "furioso", "furiosa", "revoltado", "revoltada",
        "indignado", "indignada",
        "cancelar conta", "cancelar assinatura", "encerrar conta",
        "fechar conta", "deletar conta", "cancelamento",
        "reclamação", "reclamacao", "quero reclamar",
    ],
}

ESCALATION_PHRASES = [
    "not happy with", "very disappointed", "extremely frustrated",
    "this is unacceptable", "i want to speak", "i need to speak",
    "i demand", "i require a refund", "give me my money",
    "where is my money", "fix this now", "resolve this immediately",
    "nao estou satisfeito", "não estou satisfeito",
    "muito insatisfeito", "muito insatisfeita",
    "quero meu dinheiro de volta", "me devolve o dinheiro",
    "preciso falar com", "quero falar com",
    "exijo um reembolso", "quero cancelar",
    "isso é um absurdo", "isso e um absurdo",
    "me sinto lesado", "me sinto lesada",
    "vou no procon", "vou reclamar",
]

# MCP configuration (for future use)
MCP_SERVERS: List[str] = []

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

# Default settings
DEFAULT_CONFIG: Dict[str, Any] = {
    "execution_mode": "deterministic" if not USE_LLM else "llm",
    "memory_enabled": ENABLE_MEMORY,
    "knowledge_source": "crewai" if ENABLE_CREWAI_KNOWLEDGE else "local",
    "prompts_enabled": ENABLE_PROMPT_TEMPLATES,
    "mcp_enabled": ENABLE_MCP,
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

