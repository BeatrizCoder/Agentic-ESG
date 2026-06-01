"""Data persistence layer for support tickets and feedback."""

import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from pydantic import BaseModel
import logging

# Database imports (optional)
try:
    from sqlalchemy import create_engine, Column, String, Integer, Boolean, Float, Text, DateTime, JSON
    from sqlalchemy.ext.declarative import declarative_base
    from sqlalchemy.orm import sessionmaker
    SQLALCHEMY_AVAILABLE = True
except ImportError:
    SQLALCHEMY_AVAILABLE = False

from .config import DATABASE_PROVIDER, DATABASE_URL

logger = logging.getLogger(__name__)

# SQLAlchemy setup (if available)
if SQLALCHEMY_AVAILABLE:
    Base = declarative_base()

    class RefundDB(Base):
        """SQLAlchemy model for refund records."""
        __tablename__ = "refunds"

        id = Column(Integer, primary_key=True, autoincrement=True)
        order_number = Column(String(20), unique=True, nullable=False, index=True)
        customer_email = Column(String(200))
        customer_name = Column(String(200))
        status = Column(String(20), nullable=False)
        valor = Column(Float, nullable=False)
        produto = Column(String(200), nullable=False)
        solicitado_em = Column(String(20))
        aprovado_em = Column(String(20))
        previsao_credito = Column(String(20))
        banco_processou = Column(Integer, default=0)
        motivo_negacao = Column(Text)
        created_at = Column(String(20))

    class ObservabilityEventDB(Base):
        """SQLAlchemy model for per-step observability events."""
        __tablename__ = "observability_events"

        id = Column(Integer, primary_key=True, autoincrement=True)
        reference_id = Column(String, index=True, nullable=False)
        step_name = Column(String, nullable=False)
        agent_name = Column(String, default="")
        tool_name = Column(String, default="")
        timestamp = Column(DateTime, default=datetime.utcnow)
        latency_ms = Column(Float, default=0.0)
        input_tokens = Column(Integer, default=0)
        output_tokens = Column(Integer, default=0)
        total_tokens = Column(Integer, default=0)
        cost_usd = Column(Float, default=0.0)
        model = Column(String, default="")
        execution_mode = Column(String, default="deterministic")
        cache_used = Column(Boolean, default=False)
        status = Column(String, default="success")
        success = Column(Boolean, default=True)
        error = Column(String, default="")
        details = Column(Text, default="{}")
        created_at = Column(DateTime, default=datetime.utcnow)

    class TicketObservabilityDB(Base):
        """SQLAlchemy model for per-ticket observability summary."""
        __tablename__ = "ticket_observability"

        reference_id = Column(String, primary_key=True)
        total_tokens = Column(Integer, default=0)
        total_cost_usd = Column(Float, default=0.0)
        wall_time_sec = Column(Float, default=0.0)
        step_count = Column(Integer, default=0)
        llm_calls = Column(Integer, default=0)
        deterministic_calls = Column(Integer, default=0)
        api_calls = Column(Integer, default=0)
        knowledge_snippets = Column(Integer, default=0)
        quality_grade = Column(String, default="")
        quality_overall = Column(Float, default=0.0)
        hallucination_detected = Column(Boolean, default=False)
        created_at = Column(DateTime, default=datetime.utcnow)

    class PendingAction(Base):
        """SQLAlchemy model for orders awaiting customer action."""
        __tablename__ = "pending_actions"

        order_number = Column(String(20), primary_key=True)
        ticket_id = Column(String(50), nullable=False)
        status = Column(String(50), nullable=False)
        action_required = Column(String(50), nullable=False)
        product = Column(String(200), nullable=False)
        valor = Column(Float, nullable=False)
        description = Column(Text, nullable=False)
        opened_at = Column(String(20), nullable=False)
        deadline = Column(String(20), nullable=True)
        urgency = Column(String(20), default="medium")
        additional_info = Column(Text, default="{}")

    class SupportTicketDB(Base):
        """SQLAlchemy model for support tickets."""
        __tablename__ = "support_tickets"

        reference_id = Column(String(50), primary_key=True)
        inquiry = Column(Text, nullable=False)
        category = Column(String(100), nullable=False)
        category_confidence = Column(Integer, nullable=False)
        sentiment = Column(String(50), nullable=False)
        sentiment_confidence = Column(Integer, nullable=False)
        urgency = Column(String(20), nullable=False)
        articles = Column(JSON, nullable=False)
        response = Column(Text, nullable=False)
        response_confidence = Column(Integer, nullable=False)
        escalation_required = Column(Boolean, nullable=False)
        escalation_reason = Column(Text, nullable=False)
        triggered_keyword = Column(String(100))
        steps = Column(JSON, nullable=False)
        knowledge_source = Column(String(50))
        memory_saved = Column(Boolean, default=False)
        execution_mode = Column(String(20), default="deterministic")
        prompt_template_used = Column(String(100))
        skills_used = Column(JSON, default=list)
        tools_used = Column(JSON, default=list)
        cache_used = Column(Boolean, default=False)
        status = Column(String(30), default="completed")
        created_at = Column(DateTime, nullable=False)
        updated_at = Column(DateTime, nullable=False)
        feedback = Column(JSON)
        run_id = Column(String(36))
        execution_time_ms = Column(Integer, default=0)
        api_tags = Column(JSON, default=list)
        quality_evaluation = Column(JSON, default=dict)
        pending_action = Column(JSON, default=dict)
        user_id = Column(String, default="anonymous")
        is_historical = Column(Boolean, default=False)


class SupportTicketData(BaseModel):
    """Data model for support ticket persistence."""
    reference_id: str
    inquiry: str
    category: str
    category_confidence: int
    sentiment: str
    sentiment_confidence: int
    urgency: str
    articles: List[str]
    response: str
    response_confidence: int
    escalation_required: bool
    escalation_reason: str
    triggered_keyword: Optional[str] = None
    steps: List[Dict[str, Any]]
    knowledge_source: Optional[str] = None
    memory_saved: bool = False
    execution_mode: str = "deterministic"
    prompt_template_used: Optional[str] = None
    skills_used: List[str] = []
    tools_used: List[str] = []
    cache_used: bool = False
    status: str = "completed"  # completed, pending_human_review, approved, rejected
    created_at: str
    updated_at: str
    feedback: Optional[Any] = None
    run_id: Optional[str] = None
    execution_time_ms: int = 0
    wall_time_sec: Optional[float] = None
    token_usage: Dict[str, Any] = {}
    cost_usd: float = 0.0
    api_tags: List[str] = []
    quality_evaluation: Dict[str, Any] = {}
    pending_action: Dict[str, Any] = {}
    user_id: str = "anonymous"


class DataStore:
    """Abstract data store supporting both JSON and PostgreSQL backends."""

    def __init__(self, data_dir: str = "src/aamad/data"):
        self.data_dir = data_dir
        self.tickets_file = os.path.join(data_dir, "tickets.json")
        self.use_database = DATABASE_PROVIDER.lower() in ("postgres", "sqlite") and SQLALCHEMY_AVAILABLE

        if self.use_database:
            is_postgres = DATABASE_URL.startswith("postgresql")
            if is_postgres:
                self.engine = create_engine(
                    DATABASE_URL,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                )
                logger.info("Using PostgreSQL database")
            else:
                self.engine = create_engine(
                    DATABASE_URL,
                    connect_args={"check_same_thread": False},
                )
                logger.info("Using SQLite database")
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            self._migrate_pending_actions_v2()
            Base.metadata.create_all(bind=self.engine)
            self._migrate_add_api_tags()
            self._migrate_add_pending_action()
            self._migrate_add_user_id()
            self._migrate_add_is_historical()
            self._seed_refunds()
            self._seed_pending_actions()
            self.seed_historical_tickets()
            logger.info("Database tables created/verified")
        else:
            os.makedirs(data_dir, exist_ok=True)
            self._ensure_data_file()
            logger.info("Using JSON file storage for data persistence")

    def _migrate_pending_actions_v2(self):
        """Drop pending_actions table if it has the old v1 schema (action_type column)."""
        try:
            from sqlalchemy import inspect as _inspect, text as _text
            insp = _inspect(self.engine)
            if 'pending_actions' in insp.get_table_names():
                col_names = [c['name'] for c in insp.get_columns('pending_actions')]
                if 'action_type' in col_names:
                    with self.engine.connect() as conn:
                        conn.execute(_text("DROP TABLE pending_actions"))
                        conn.commit()
                    logger.info("Dropped pending_actions v1 table (schema migration to v2)")
        except Exception as e:
            logger.warning("pending_actions v2 migration check failed: %s", e)

    def _migrate_add_pending_action(self):
        """Add pending_action column to existing support_tickets rows."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE support_tickets ADD COLUMN pending_action JSON"
                    )
                )
                conn.commit()
        except Exception:
            pass  # Column already exists

    def _migrate_add_user_id(self):
        """Add user_id column to existing support_tickets rows."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE support_tickets ADD COLUMN user_id VARCHAR(200) DEFAULT 'anonymous'"
                    )
                )
                conn.commit()
        except Exception:
            pass  # Column already exists

    def _migrate_add_is_historical(self):
        """Add is_historical column to existing support_tickets rows."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE support_tickets ADD COLUMN is_historical BOOLEAN DEFAULT FALSE"
                    )
                )
                conn.commit()
                logger.info("Added is_historical column to support_tickets")
        except Exception:
            pass  # Column already exists

    def seed_historical_tickets(self) -> int:
        """Seed historical_seed.json into Neon as is_historical=TRUE rows (idempotent)."""
        import json as _json
        from pathlib import Path as _Path
        from sqlalchemy import text as _text

        logger.info("Starting historical seed check...")

        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            logger.info("No database configured — skipping historical seed")
            return 0

        with self.SessionLocal() as session:
            count = session.execute(
                _text("SELECT COUNT(*) FROM support_tickets WHERE is_historical = TRUE")
            ).scalar() or 0

        logger.info("Historical tickets in DB: %d", count)

        seed_path = _Path("src/aamad/data/historical_seed.json")
        logger.info("Seed file exists: %s", seed_path.exists())
        logger.info("Seed file path: %s", seed_path.absolute())

        if not seed_path.exists():
            logger.warning("historical_seed.json not found — cannot seed historical data")
            return 0

        logger.info("Seeding historical tickets...")
        try:
            with open(seed_path, encoding="utf-8") as f:
                rows = _json.load(f)
        except Exception as e:
            logger.error("Failed to read historical_seed.json: %s", e)
            return 0

        def _coerce(val, default):
            if val is None:
                return default
            if isinstance(val, str):
                try:
                    return _json.loads(val)
                except Exception:
                    return default
            return val

        inserted = 0
        with self.SessionLocal() as session:
            for r in rows:
                ref_id = r.get("reference_id", "")
                if not ref_id:
                    continue
                existing = session.execute(
                    _text("SELECT reference_id FROM support_tickets WHERE reference_id = :rid"),
                    {"rid": ref_id},
                ).fetchone()
                if existing:
                    continue

                created_raw = r.get("created_at") or r.get("updated_at") or ""
                try:
                    created_dt = datetime.fromisoformat(created_raw.replace("Z", "+00:00"))
                except Exception:
                    created_dt = datetime.utcnow()

                updated_raw = r.get("updated_at") or created_raw
                try:
                    updated_dt = datetime.fromisoformat(updated_raw.replace("Z", "+00:00"))
                except Exception:
                    updated_dt = created_dt

                session.execute(_text("""
                    INSERT INTO support_tickets (
                        reference_id, inquiry, category, category_confidence,
                        sentiment, sentiment_confidence, urgency,
                        articles, response, response_confidence,
                        escalation_required, escalation_reason, triggered_keyword,
                        steps, knowledge_source, memory_saved, execution_mode,
                        tools_used, cache_used, status,
                        created_at, updated_at, feedback, run_id, execution_time_ms,
                        api_tags, quality_evaluation, pending_action, user_id, is_historical
                    ) VALUES (
                        :reference_id, :inquiry, :category, :category_confidence,
                        :sentiment, :sentiment_confidence, :urgency,
                        :articles, :response, :response_confidence,
                        :escalation_required, :escalation_reason, :triggered_keyword,
                        :steps, :knowledge_source, :memory_saved, :execution_mode,
                        :tools_used, :cache_used, :status,
                        :created_at, :updated_at, :feedback, :run_id, :execution_time_ms,
                        :api_tags, :quality_evaluation, :pending_action, :user_id, TRUE
                    )
                """), {
                    "reference_id": ref_id,
                    "inquiry": r.get("inquiry", ""),
                    "category": r.get("category", ""),
                    "category_confidence": r.get("category_confidence") or 0,
                    "sentiment": r.get("sentiment", ""),
                    "sentiment_confidence": r.get("sentiment_confidence") or 0,
                    "urgency": r.get("urgency", ""),
                    "articles": _json.dumps(_coerce(r.get("articles"), [])),
                    "response": r.get("response", ""),
                    "response_confidence": r.get("response_confidence") or 0,
                    "escalation_required": bool(r.get("escalation_required", False)),
                    "escalation_reason": r.get("escalation_reason", ""),
                    "triggered_keyword": r.get("triggered_keyword"),
                    "steps": _json.dumps(_coerce(r.get("steps"), [])),
                    "knowledge_source": r.get("knowledge_source", ""),
                    "memory_saved": bool(r.get("memory_saved", False)),
                    "execution_mode": r.get("execution_mode", "deterministic"),
                    "tools_used": _json.dumps(_coerce(r.get("tools_used"), [])),
                    "cache_used": bool(r.get("cache_used", False)),
                    "status": r.get("status", "completed"),
                    "created_at": created_dt,
                    "updated_at": updated_dt,
                    "feedback": _json.dumps(_coerce(r.get("feedback"), None)) if r.get("feedback") is not None else None,
                    "run_id": r.get("run_id"),
                    "execution_time_ms": r.get("execution_time_ms") or 0,
                    "api_tags": _json.dumps(_coerce(r.get("api_tags"), [])),
                    "quality_evaluation": _json.dumps(_coerce(r.get("quality_evaluation"), {})),
                    "pending_action": _json.dumps(_coerce(r.get("pending_action"), {})),
                    "user_id": r.get("user_id", "historical"),
                })
                inserted += 1

            session.commit()

        logger.info("Seeded %d historical tickets into Neon", inserted)
        return inserted

    def _migrate_add_api_tags(self):
        """Add api_tags and quality_evaluation columns to existing databases."""
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE support_tickets ADD COLUMN api_tags JSON"
                    )
                )
                conn.commit()
        except Exception:
            pass  # Column already exists
        try:
            with self.engine.connect() as conn:
                conn.execute(
                    __import__("sqlalchemy").text(
                        "ALTER TABLE support_tickets ADD COLUMN quality_evaluation JSON"
                    )
                )
                conn.commit()
        except Exception:
            pass  # Column already exists

    def _ensure_data_file(self):
        """Ensure the JSON data file exists."""
        if not os.path.exists(self.tickets_file):
            with open(self.tickets_file, 'w') as f:
                json.dump({}, f)

    def _load_tickets(self) -> Dict[str, Dict[str, Any]]:
        """Load tickets from JSON file."""
        try:
            with open(self.tickets_file, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def _save_tickets(self, tickets: Dict[str, Dict[str, Any]]):
        """Save tickets to JSON file."""
        with open(self.tickets_file, 'w') as f:
            json.dump(tickets, f, indent=2)

    def _db_to_pydantic(self, db_ticket) -> SupportTicketData:
        """Convert database model to Pydantic model."""
        return SupportTicketData(
            reference_id=db_ticket.reference_id,
            inquiry=db_ticket.inquiry,
            category=db_ticket.category,
            category_confidence=db_ticket.category_confidence,
            sentiment=db_ticket.sentiment,
            sentiment_confidence=db_ticket.sentiment_confidence,
            urgency=db_ticket.urgency,
            articles=db_ticket.articles,
            response=db_ticket.response,
            response_confidence=db_ticket.response_confidence,
            escalation_required=db_ticket.escalation_required,
            escalation_reason=db_ticket.escalation_reason,
            triggered_keyword=db_ticket.triggered_keyword,
            steps=db_ticket.steps,
            knowledge_source=db_ticket.knowledge_source,
            memory_saved=db_ticket.memory_saved,
            execution_mode=db_ticket.execution_mode,
            prompt_template_used=db_ticket.prompt_template_used,
            skills_used=db_ticket.skills_used or [],
            tools_used=db_ticket.tools_used or [],
            cache_used=db_ticket.cache_used,
            status=db_ticket.status,
            created_at=db_ticket.created_at.isoformat(),
            updated_at=db_ticket.updated_at.isoformat(),
            feedback=db_ticket.feedback,
            run_id=db_ticket.run_id,
            execution_time_ms=db_ticket.execution_time_ms or 0,
            wall_time_sec=round((db_ticket.execution_time_ms or 0) / 1000, 3),
            api_tags=db_ticket.api_tags or [],
            quality_evaluation=db_ticket.quality_evaluation or {},
            pending_action=db_ticket.pending_action or {},
            user_id=db_ticket.user_id or "anonymous",
        )

    _REFUND_SEED = [
        {"order_number": "11111", "customer_email": "cliente@email.com",
         "customer_name": "Cliente Teste", "status": "aprovado", "valor": 150.00,
         "produto": "Tênis Nike Air", "solicitado_em": "2026-05-08",
         "aprovado_em": "2026-05-10", "previsao_credito": "2026-05-17",
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-08"},
        {"order_number": "22222", "customer_email": "cliente2@email.com",
         "customer_name": "Cliente Dois", "status": "pendente", "valor": 89.90,
         "produto": "Camiseta Adidas", "solicitado_em": "2026-05-13",
         "aprovado_em": None, "previsao_credito": None,
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-13"},
        {"order_number": "33333", "customer_email": "cliente3@email.com",
         "customer_name": "Cliente Três", "status": "negado", "valor": 45.00,
         "produto": "Acessório USB", "solicitado_em": "2026-05-01",
         "aprovado_em": None, "previsao_credito": None, "banco_processou": 0,
         "motivo_negacao": "Produto aberto e utilizado fora da política de devolução",
         "created_at": "2026-05-01"},
        {"order_number": "44444", "customer_email": "cliente4@email.com",
         "customer_name": "Cliente Quatro", "status": "processado", "valor": 299.00,
         "produto": "Smartwatch", "solicitado_em": "2026-05-05",
         "aprovado_em": "2026-05-07", "previsao_credito": "2026-05-12",
         "banco_processou": 1, "motivo_negacao": None, "created_at": "2026-05-05"},
        {"order_number": "55555", "customer_email": "cliente5@email.com",
         "customer_name": "Cliente Cinco", "status": "aprovado", "valor": 199.90,
         "produto": "Mochila Escolar", "solicitado_em": "2026-05-10",
         "aprovado_em": "2026-05-12", "previsao_credito": "2026-05-19",
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-10"},
        {"order_number": "66666", "customer_email": "cliente6@email.com",
         "customer_name": "Cliente Seis", "status": "pendente", "valor": 520.00,
         'produto': 'Monitor 24"', "solicitado_em": "2026-05-14",
         "aprovado_em": None, "previsao_credito": None,
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-14"},
        {"order_number": "77777", "customer_email": "cliente7@email.com",
         "customer_name": "Cliente Sete", "status": "processado", "valor": 35.00,
         "produto": "Carregador USB-C", "solicitado_em": "2026-05-03",
         "aprovado_em": "2026-05-05", "previsao_credito": "2026-05-10",
         "banco_processou": 1, "motivo_negacao": None, "created_at": "2026-05-03"},
        {"order_number": "88888", "customer_email": "cliente8@email.com",
         "customer_name": "Cliente Oito", "status": "aprovado", "valor": 750.00,
         "produto": "iPhone Case Premium", "solicitado_em": "2026-05-11",
         "aprovado_em": "2026-05-13", "previsao_credito": "2026-05-20",
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-11"},
        {"order_number": "99999", "customer_email": "cliente9@email.com",
         "customer_name": "Cliente Nove", "status": "negado", "valor": 180.00,
         "produto": "Perfume Importado", "solicitado_em": "2026-05-02",
         "aprovado_em": None, "previsao_credito": None, "banco_processou": 0,
         "motivo_negacao": "Item fora do prazo de devolução de 30 dias",
         "created_at": "2026-05-02"},
        {"order_number": "10000", "customer_email": "cliente10@email.com",
         "customer_name": "Cliente Dez", "status": "em_analise", "valor": 440.00,
         "produto": "Notebook Sleeve", "solicitado_em": "2026-05-15",
         "aprovado_em": None, "previsao_credito": None,
         "banco_processou": 0, "motivo_negacao": None, "created_at": "2026-05-15"},
    ]

    _PENDING_ACTION_SEED = [
        {
            "order_number": "77701",
            "ticket_id": "ESC-2026-7701",
            "status": "AWAITING_PHOTO",
            "action_required": "photo_upload",
            "product": "Tênis Nike Air Max",
            "valor": 450.00,
            "description": (
                "Produto chegou com solado rachado. "
                "Caso aberto e aprovado para troca/reembolso. "
                "Aguardando foto do defeito para prosseguir."
            ),
            "opened_at": "2026-05-10",
            "deadline": "2026-05-24",
            "urgency": "high",
            "additional_info": json.dumps({
                "defect": "solado rachado",
                "resolution": "troca ou reembolso",
                "photos_needed": 2,
                "instructions": "Fotografe o defeito com boa iluminação",
            }),
        },
        {
            "order_number": "77702",
            "ticket_id": "DEV-2026-7702",
            "status": "LABEL_EXPIRED",
            "action_required": "generate_new_label",
            "product": "Smartwatch Samsung Galaxy Watch 6",
            "valor": 899.00,
            "description": (
                "Devolução solicitada e aprovada. "
                "Etiqueta dos Correios gerada em 29/04 expirou em 19/05. "
                "Cliente precisa gerar uma nova etiqueta pelo sistema."
            ),
            "opened_at": "2026-04-29",
            "deadline": "2026-05-30",
            "urgency": "high",
            "additional_info": json.dumps({
                "label_generated": "2026-04-29",
                "label_expired": "2026-05-19",
                "return_reason": "produto com defeito",
                "new_label_url": "app.supportai.com/devolucoes/nova-etiqueta",
            }),
        },
        {
            "order_number": "77703",
            "ticket_id": "TRK-2026-7703",
            "status": "AWAITING_RETURN_SHIPMENT",
            "action_required": "ship_product",
            "product": "Notebook Dell Inspiron 15",
            "valor": 3200.00,
            "description": (
                "Troca aprovada por defeito de fábrica. "
                "Cliente precisa enviar o produto de volta. "
                "Prazo de 7 dias já expirou em 17/05."
            ),
            "opened_at": "2026-05-10",
            "deadline": "2026-05-17",
            "urgency": "high",
            "additional_info": json.dumps({
                "exchange_approved": "2026-05-10",
                "deadline_expired": True,
                "defect": "tela piscando ao iniciar",
                "shipping_instructions": "Use a embalagem original se possível",
                "pickup_available": True,
            }),
        },
        {
            "order_number": "77704",
            "ticket_id": "BIL-2026-7704",
            "status": "AWAITING_DOCUMENTATION",
            "action_required": "send_proof",
            "product": "iPhone 15 Case Premium",
            "valor": 189.00,
            "description": (
                "Contestação de cobrança duplicada aberta em 05/05. "
                "Aguardando comprovante de pagamento (extrato bancário) "
                "para prosseguir com o estorno."
            ),
            "opened_at": "2026-05-05",
            "deadline": "2026-05-26",
            "urgency": "medium",
            "additional_info": json.dumps({
                "dispute_reason": "cobrança duplicada",
                "amount_disputed": 189.00,
                "documents_needed": [
                    "Extrato bancário do período",
                    "Comprovante de pagamento",
                ],
                "dispute_opened": "2026-05-05",
            }),
        },
        {
            "order_number": "77705",
            "ticket_id": "DEL-2026-7705",
            "status": "DELIVERY_FAILED",
            "action_required": "reschedule_delivery",
            "product": "Monitor LG 27 4K UltraFine",
            "valor": 2100.00,
            "description": (
                "2 tentativas de entrega sem sucesso. "
                "Última tentativa: 16/05. "
                "Produto retorna ao estoque em 25/05 "
                "se não houver reagendamento."
            ),
            "opened_at": "2026-05-14",
            "deadline": "2026-05-25",
            "urgency": "high",
            "additional_info": json.dumps({
                "attempts": 2,
                "last_attempt": "2026-05-16",
                "return_deadline": "2026-05-25",
                "pickup_available": True,
                "cd_address": "Av. Marginal Tietê, 1000 - São Paulo",
                "reschedule_url": "app.supportai.com/entregas/reagendar",
            }),
        },
        {
            "order_number": "77706",
            "ticket_id": "WAR-2026-7706",
            "status": "UNDER_TECHNICAL_ANALYSIS",
            "action_required": "wait_for_report",
            "product": "Fone Sony WH-1000XM5",
            "valor": 1650.00,
            "description": (
                "Produto enviado para assistência técnica em 08/05. "
                "Defeito: cancelamento de ruído não funciona. "
                "Laudo técnico previsto para 22/05."
            ),
            "opened_at": "2026-05-08",
            "deadline": "2026-05-22",
            "urgency": "low",
            "additional_info": json.dumps({
                "defect": "cancelamento de ruído ativo não funciona",
                "sent_to_service": "2026-05-08",
                "report_deadline": "2026-05-22",
                "warranty_valid": True,
                "service_center": "Sony Assistência Técnica SP",
                "protocol": "SOA-2026-77706",
            }),
        },
        {
            "order_number": "77707",
            "ticket_id": "CAN-2026-7707",
            "status": "AWAITING_RETURN",
            "action_required": "return_product",
            "product": "Cafeteira Nespresso Vertuo Plus",
            "valor": 620.00,
            "description": (
                "Cancelamento aprovado em 12/05. "
                "Prazo para devolução do produto: até 19/05 (hoje!). "
                "Reembolso de R$620,00 liberado após recebimento."
            ),
            "opened_at": "2026-05-12",
            "deadline": "2026-05-19",
            "urgency": "high",
            "additional_info": json.dumps({
                "cancellation_approved": "2026-05-12",
                "return_deadline": "2026-05-19",
                "deadline_today": True,
                "refund_amount": 620.00,
                "refund_after_receipt": True,
                "return_label_url": "app.supportai.com/cancelamentos/etiqueta",
            }),
        },
    ]

    def _seed_refunds(self):
        """Insert seed refund records if the table is empty."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return
        db = self.SessionLocal()
        try:
            count = db.query(RefundDB).count()
            if count == 0:
                for row in self._REFUND_SEED:
                    db.add(RefundDB(**row))
                db.commit()
                logger.info("Seeded %d refund records", len(self._REFUND_SEED))
        except Exception as e:
            db.rollback()
            logger.error("Error seeding refunds: %s", e)
        finally:
            db.close()

    def get_refund(self, order_number: str) -> Optional[Dict[str, Any]]:
        """Return refund record for an order number, or None if not found."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return None
        db = self.SessionLocal()
        try:
            row = db.query(RefundDB).filter(
                RefundDB.order_number == str(order_number)
            ).first()
            if not row:
                return None
            return {
                "order_number": row.order_number,
                "customer_name": row.customer_name,
                "status": row.status,
                "valor": row.valor,
                "produto": row.produto,
                "solicitado_em": row.solicitado_em,
                "aprovado_em": row.aprovado_em or "",
                "previsao_credito": row.previsao_credito or "",
                "banco_processou": bool(row.banco_processou),
                "motivo_negacao": row.motivo_negacao or "",
            }
        except Exception as e:
            logger.error("Error fetching refund for order %s: %s", order_number, e)
            return None
        finally:
            db.close()

    def _seed_pending_actions(self):
        """Insert seed pending-action records if the table is empty."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return
        db = self.SessionLocal()
        try:
            count = db.query(PendingAction).count()
            if count == 0:
                for row in self._PENDING_ACTION_SEED:
                    db.add(PendingAction(**row))
                db.commit()
                logger.info("Seeded %d pending action records", len(self._PENDING_ACTION_SEED))
        except Exception as e:
            db.rollback()
            logger.error("Error seeding pending actions: %s", e)
        finally:
            db.close()

    def get_pending_action(self, order_number: str) -> Optional[Dict[str, Any]]:
        """Return pending-action record for an order number, or None if not found."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return None
        db = self.SessionLocal()
        try:
            row = db.query(PendingAction).filter(
                PendingAction.order_number == str(order_number)
            ).first()
            if not row:
                return None
            return {
                "found": True,
                "order_number": row.order_number,
                "ticket_id": row.ticket_id,
                "status": row.status,
                "action_required": row.action_required,
                "product": row.product,
                "valor": row.valor,
                "description": row.description,
                "opened_at": row.opened_at,
                "deadline": row.deadline,
                "urgency": row.urgency,
                "additional_info": json.loads(row.additional_info or "{}"),
            }
        except Exception as e:
            logger.error("Error fetching pending action for order %s: %s", order_number, e)
            return None
        finally:
            db.close()

    def save_ticket(self, ticket_data: SupportTicketData):
        """Save a support ticket."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                # Convert Pydantic to database model
                db_ticket = SupportTicketDB(
                    reference_id=ticket_data.reference_id,
                    inquiry=ticket_data.inquiry,
                    category=ticket_data.category,
                    category_confidence=ticket_data.category_confidence,
                    sentiment=ticket_data.sentiment,
                    sentiment_confidence=ticket_data.sentiment_confidence,
                    urgency=ticket_data.urgency,
                    articles=ticket_data.articles,
                    response=ticket_data.response,
                    response_confidence=ticket_data.response_confidence,
                    escalation_required=ticket_data.escalation_required,
                    escalation_reason=ticket_data.escalation_reason,
                    triggered_keyword=ticket_data.triggered_keyword,
                    steps=ticket_data.steps,
                    knowledge_source=ticket_data.knowledge_source,
                    memory_saved=ticket_data.memory_saved,
                    execution_mode=ticket_data.execution_mode,
                    prompt_template_used=ticket_data.prompt_template_used,
                    skills_used=ticket_data.skills_used,
                    tools_used=ticket_data.tools_used,
                    cache_used=ticket_data.cache_used,
                    status=ticket_data.status,
                    created_at=datetime.fromisoformat(ticket_data.created_at),
                    updated_at=datetime.fromisoformat(ticket_data.updated_at),
                    feedback=ticket_data.feedback,
                    run_id=ticket_data.run_id,
                    execution_time_ms=ticket_data.execution_time_ms,
                    api_tags=ticket_data.api_tags or [],
                    quality_evaluation=ticket_data.quality_evaluation or {},
                    pending_action=ticket_data.pending_action or {},
                    user_id=ticket_data.user_id,
                )
                db.merge(db_ticket)  # Use merge to handle updates
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Database error saving ticket: {e}")
                raise
            finally:
                db.close()
        else:
            # JSON fallback
            tickets = self._load_tickets()
            tickets[ticket_data.reference_id] = ticket_data.model_dump()
            self._save_tickets(tickets)

    def get_ticket(self, reference_id: str) -> Optional[SupportTicketData]:
        """Get a support ticket by reference ID."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_ticket = db.query(SupportTicketDB).filter(SupportTicketDB.reference_id == reference_id).first()
                return self._db_to_pydantic(db_ticket) if db_ticket else None
            except Exception as e:
                logger.error(f"Database error getting ticket: {e}")
                return None
            finally:
                db.close()
        else:
            # JSON fallback
            tickets = self._load_tickets()
            ticket_data = tickets.get(reference_id)
            if ticket_data:
                return SupportTicketData(**ticket_data)
            return None

    def update_ticket_quality(
        self,
        run_id: str,
        ticket_summary: str,
        action_needed: str,
        key_facts: list,
        quality_evaluation: dict,
    ) -> None:
        """Persist background evaluation results once the crew finishes.

        Looks up the ticket by run_id (always available) rather than
        reference_id (which is generated in routes.py after the flow ends).
        """
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return
        with self.SessionLocal() as session:
            ticket = session.query(SupportTicketDB).filter(
                SupportTicketDB.run_id == run_id
            ).first()
            if ticket:
                # Embed summary fields inside the existing quality_evaluation JSON
                combined = dict(quality_evaluation)
                combined["ticket_summary"] = ticket_summary
                combined["action_needed"] = action_needed
                combined["key_facts"] = key_facts
                ticket.quality_evaluation = combined
                session.commit()
                logger.info("Quality saved for run_id=%s ref=%s", run_id, ticket.reference_id)
            else:
                logger.warning("update_ticket_quality: no ticket found for run_id=%s", run_id)

    def update_ticket_status(self, reference_id: str, status: str, feedback: Optional[Dict[str, Any]] = None):
        """Update ticket status and optionally add feedback."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_ticket = db.query(SupportTicketDB).filter(SupportTicketDB.reference_id == reference_id).first()
                if db_ticket:
                    db_ticket.status = status
                    db_ticket.updated_at = datetime.now()
                    if feedback:
                        db_ticket.feedback = feedback
                    db.commit()
                    return True
                return False
            except Exception as e:
                db.rollback()
                logger.error(f"Database error updating ticket: {e}")
                return False
            finally:
                db.close()
        else:
            # JSON fallback
            tickets = self._load_tickets()
            if reference_id in tickets:
                tickets[reference_id]["status"] = status
                tickets[reference_id]["updated_at"] = datetime.now().isoformat()
                if feedback:
                    tickets[reference_id]["feedback"] = feedback
                self._save_tickets(tickets)
                return True
            return False

    def save_feedback(
        self,
        reference_id: str,
        helpful: bool,
        feedback_reason: str = None,
    ) -> bool:
        """Save CSAT feedback for a ticket. Stores 'positive'/'negative' in feedback column."""
        value = "positive" if helpful else "negative"
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_ticket = (
                    db.query(SupportTicketDB)
                    .filter(SupportTicketDB.reference_id == reference_id)
                    .first()
                )
                if not db_ticket:
                    logger.warning("save_feedback: ticket not found: %s", reference_id)
                    return False
                db_ticket.feedback = value
                if feedback_reason:
                    db_ticket.feedback = {"value": value, "reason": feedback_reason}
                db_ticket.updated_at = datetime.now()
                db.commit()
                logger.info(
                    "Feedback saved: %s → %s", reference_id, value
                )
                return True
            except Exception as e:
                db.rollback()
                logger.error("Database error saving feedback: %s", e)
                return False
            finally:
                db.close()
        else:
            tickets = self._load_tickets()
            if reference_id in tickets:
                tickets[reference_id]["feedback"] = value
                tickets[reference_id]["updated_at"] = datetime.now().isoformat()
                self._save_tickets(tickets)
                return True
            return False

    # ── Observability persistence ─────────────────────────────────────────────

    def save_observability_event(
        self,
        reference_id: str,
        step_name: str,
        agent_name: str = "",
        tool_name: str = "",
        latency_ms: float = 0.0,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost_usd: float = 0.0,
        model: str = "",
        execution_mode: str = "deterministic",
        cache_used: bool = False,
        status: str = "success",
        error: str = "",
        details: dict = None,
    ) -> None:
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return
        with self.SessionLocal() as session:
            event = ObservabilityEventDB(
                reference_id=reference_id,
                step_name=step_name,
                agent_name=agent_name,
                tool_name=tool_name,
                latency_ms=latency_ms,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens,
                cost_usd=cost_usd,
                model=model,
                execution_mode=execution_mode,
                cache_used=cache_used,
                status=status,
                success=(status == "success"),
                error=error,
                details=json.dumps(details or {}),
            )
            session.add(event)
            session.commit()

    def remap_observability_events(self, old_ref: str, new_ref: str) -> None:
        if not self.use_database or not SQLALCHEMY_AVAILABLE or old_ref == new_ref:
            return
        from sqlalchemy import text as _text
        with self.SessionLocal() as session:
            session.execute(
                _text(
                    "UPDATE observability_events "
                    "SET reference_id = :new WHERE reference_id = :old"
                ),
                {"new": new_ref, "old": old_ref},
            )
            session.commit()

    def save_ticket_observability(
        self,
        reference_id: str,
        total_tokens: int,
        total_cost_usd: float,
        wall_time_sec: float,
        step_count: int,
        llm_calls: int,
        deterministic_calls: int,
        api_calls: int,
        knowledge_snippets: int = 0,
        quality_grade: str = "",
        quality_overall: float = 0.0,
        hallucination_detected: bool = False,
    ) -> None:
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return
        with self.SessionLocal() as session:
            obs = TicketObservabilityDB(
                reference_id=reference_id,
                total_tokens=total_tokens,
                total_cost_usd=total_cost_usd,
                wall_time_sec=wall_time_sec,
                step_count=step_count,
                llm_calls=llm_calls,
                deterministic_calls=deterministic_calls,
                api_calls=api_calls,
                knowledge_snippets=knowledge_snippets,
                quality_grade=quality_grade,
                quality_overall=quality_overall,
                hallucination_detected=hallucination_detected,
            )
            session.merge(obs)
            session.commit()

    def get_observability_by_ticket(self, reference_id: str) -> List[Dict[str, Any]]:
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        with self.SessionLocal() as session:
            events = (
                session.query(ObservabilityEventDB)
                .filter(ObservabilityEventDB.reference_id == reference_id)
                .order_by(ObservabilityEventDB.timestamp)
                .all()
            )
            return [
                {
                    "step_name": e.step_name,
                    "agent_name": e.agent_name,
                    "tool_name": e.tool_name,
                    "latency_ms": e.latency_ms,
                    "input_tokens": e.input_tokens,
                    "output_tokens": e.output_tokens,
                    "total_tokens": e.total_tokens,
                    "cost_usd": e.cost_usd,
                    "model": e.model,
                    "execution_mode": e.execution_mode,
                    "cache_used": e.cache_used,
                    "status": e.status,
                    "success": e.success,
                    "error": e.error,
                    "details": json.loads(e.details or "{}"),
                    "timestamp": e.timestamp.isoformat() if e.timestamp else "",
                }
                for e in events
            ]

    def get_observability_summary(
        self,
        user_id: str = None,
        historical_only: bool = False,
    ) -> Dict[str, Any]:
        """Aggregate observability metrics, scoped to the active dataset mode."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return {}
        from sqlalchemy import func
        with self.SessionLocal() as session:
            # Build a subquery of reference_ids belonging to the active scope
            if historical_only:
                ref_ids_sq = (
                    session.query(SupportTicketDB.reference_id)
                    .filter(SupportTicketDB.is_historical == True)  # noqa: E712
                    .subquery()
                )
            elif user_id and user_id != "anonymous":
                ref_ids_sq = (
                    session.query(SupportTicketDB.reference_id)
                    .filter(
                        (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None),  # noqa: E711,E712
                        SupportTicketDB.user_id == user_id,
                    )
                    .subquery()
                )
            else:
                ref_ids_sq = (
                    session.query(SupportTicketDB.reference_id)
                    .filter(
                        (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None),  # noqa: E711,E712
                    )
                    .subquery()
                )

            scope = ObservabilityEventDB.reference_id.in_(ref_ids_sq)

            # Per-event aggregates
            total_events = session.query(ObservabilityEventDB).filter(scope).count()
            total_tickets = (
                session.query(ObservabilityEventDB.reference_id)
                .filter(scope)
                .distinct()
                .count()
            )
            avg_latency = (
                session.query(func.avg(ObservabilityEventDB.latency_ms)).filter(scope).scalar() or 0.0
            )
            total_tokens = (
                session.query(func.sum(ObservabilityEventDB.total_tokens)).filter(scope).scalar() or 0
            )
            total_cost = (
                session.query(func.sum(ObservabilityEventDB.cost_usd)).filter(scope).scalar() or 0.0
            )
            llm_calls = (
                session.query(ObservabilityEventDB)
                .filter(scope, ObservabilityEventDB.execution_mode == "llm")
                .count()
            )
            det_calls = (
                session.query(ObservabilityEventDB)
                .filter(scope, ObservabilityEventDB.execution_mode == "deterministic")
                .count()
            )
            cache_hits = (
                session.query(ObservabilityEventDB)
                .filter(scope, ObservabilityEventDB.cache_used == True)  # noqa: E712
                .count()
            )
            errors = (
                session.query(ObservabilityEventDB)
                .filter(scope, ObservabilityEventDB.success == False)  # noqa: E712
                .count()
            )

            # Per-ticket aggregates (for hallucination rate) — scoped by the same ref_ids
            ticket_obs_scope = TicketObservabilityDB.reference_id.in_(ref_ids_sq)
            total_evaluated = (
                session.query(TicketObservabilityDB)
                .filter(ticket_obs_scope, TicketObservabilityDB.quality_grade != "")
                .count()
            )
            hallucinated = (
                session.query(TicketObservabilityDB)
                .filter(ticket_obs_scope, TicketObservabilityDB.hallucination_detected == True)  # noqa: E712
                .count()
            )
            avg_wall_time = (
                session.query(func.avg(TicketObservabilityDB.wall_time_sec))
                .filter(ticket_obs_scope)
                .scalar() or 0.0
            )

            # Per-agent metrics
            from sqlalchemy import case as _case
            rows = session.query(
                ObservabilityEventDB.agent_name,
                ObservabilityEventDB.tool_name,
                func.count(ObservabilityEventDB.id).label("calls"),
                func.avg(ObservabilityEventDB.latency_ms).label("avg_latency"),
                func.sum(ObservabilityEventDB.total_tokens).label("total_tokens"),
                func.sum(ObservabilityEventDB.cost_usd).label("total_cost"),
                func.sum(_case(
                    (ObservabilityEventDB.execution_mode == "llm", 1),
                    else_=0,
                )).label("llm_calls"),
            ).filter(scope).group_by(
                ObservabilityEventDB.agent_name, ObservabilityEventDB.tool_name
            ).all()

            agent_performance: Dict[str, Any] = {}
            tool_usage: Dict[str, int] = {}
            for row in rows:
                name = row.agent_name or row.tool_name or "unknown"
                agent_performance[name] = {
                    "calls": row.calls,
                    "avg_latency_ms": round(row.avg_latency or 0, 2),
                    "total_tokens": row.total_tokens or 0,
                    "total_cost_usd": round(row.total_cost or 0, 6),
                    "llm_calls": int(row.llm_calls or 0),
                }
                if row.tool_name:
                    tool_usage[row.tool_name] = (
                        tool_usage.get(row.tool_name, 0) + row.calls
                    )

            return {
                "total_events": total_events,
                "total_tickets": total_tickets,
                "avg_latency_ms": round(avg_latency, 2),
                "llm_calls": llm_calls,
                "deterministic_calls": det_calls,
                "cache_hits": cache_hits,
                "errors": errors,
                "total_estimated_tokens": total_tokens,
                "total_cost_usd": round(total_cost, 6),
                "hallucination_rate": round(
                    hallucinated / total_evaluated * 100, 1
                ) if total_evaluated > 0 else 0.0,
                "total_evaluated": total_evaluated,
                "avg_wall_time_sec": round(avg_wall_time, 2),
                "agent_performance": agent_performance,
                "tool_usage": tool_usage,
            }

    def get_historical_tickets(self) -> List[SupportTicketData]:
        """Return all is_historical=TRUE rows from Neon."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        with self.SessionLocal() as session:
            db_tickets = (
                session.query(SupportTicketDB)
                .filter(SupportTicketDB.is_historical == True)  # noqa: E712
                .order_by(SupportTicketDB.created_at.desc())
                .all()
            )
            return [self._db_to_pydantic(t) for t in db_tickets]

    def get_all_tickets(self) -> List[SupportTicketData]:
        """Get all live (non-historical) support tickets."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_tickets = (
                    db.query(SupportTicketDB)
                    .filter(
                        (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None)  # noqa: E711
                    )
                    .all()
                )
                return [self._db_to_pydantic(ticket) for ticket in db_tickets]
            except Exception as e:
                logger.error(f"Database error getting all tickets: {e}")
                return []
            finally:
                db.close()
        else:
            # JSON fallback
            tickets = self._load_tickets()
            return [SupportTicketData(**data) for data in tickets.values()]

    def get_live_tickets(self, user_id: str = None) -> List[SupportTicketData]:
        """Return live (non-historical) tickets, optionally scoped to a single user."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        with self.SessionLocal() as session:
            q = session.query(SupportTicketDB).filter(
                (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None)  # noqa: E711
            )
            if user_id:
                q = q.filter(SupportTicketDB.user_id == user_id)
            db_tickets = q.order_by(SupportTicketDB.created_at.desc()).all()
            return [self._db_to_pydantic(t) for t in db_tickets]

    def get_user_tickets(self, user_id: str) -> List[SupportTicketData]:
        """Get live tickets for a specific user (never returns historical rows)."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        with self.SessionLocal() as session:
            db_tickets = (
                session.query(SupportTicketDB)
                .filter(SupportTicketDB.user_id == user_id)
                .filter(
                    (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None)  # noqa: E711
                )
                .order_by(SupportTicketDB.created_at.desc())
                .all()
            )
            return [self._db_to_pydantic(t) for t in db_tickets]

    def get_tickets_by_status(self, status: str) -> List[SupportTicketData]:
        """Get tickets by status."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_tickets = db.query(SupportTicketDB).filter(SupportTicketDB.status == status).all()
                return [self._db_to_pydantic(ticket) for ticket in db_tickets]
            except Exception as e:
                logger.error(f"Database error getting tickets by status: {e}")
                return []
            finally:
                db.close()
        else:
            # JSON fallback
            all_tickets = self.get_all_tickets()
            return [ticket for ticket in all_tickets if ticket.status == status]

    def get_csat_metrics(self, user_id: str = None) -> Dict[str, Any]:
        """Calculate CSAT for live tickets, optionally scoped to a single user."""
        import json as _json
        from sqlalchemy import text as _text

        empty: Dict[str, Any] = {"csat_score": None, "csat_positive": 0, "csat_negative": 0, "total_feedback": 0}
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return empty

        is_postgres = DATABASE_URL.startswith("postgresql")
        null_filter = (
            "AND feedback::text != 'null' AND feedback::text != '\"\"'"
            if is_postgres
            else "AND CAST(feedback AS TEXT) != 'null' AND CAST(feedback AS TEXT) != '\"\"'"
        )
        # Always exclude historical tickets from live CSAT
        hist_exclude = "AND (is_historical = FALSE OR is_historical IS NULL)"
        user_filter = f"AND user_id = '{user_id}'" if user_id else ""

        try:
            with self.SessionLocal() as session:
                feedback_data = session.execute(
                    _text(
                        f"SELECT feedback FROM support_tickets "
                        f"WHERE feedback IS NOT NULL {null_filter} {hist_exclude} {user_filter}"
                    )
                ).fetchall()
                logger.info("CSAT: %d feedback rows (user=%s)", len(feedback_data), user_id or "all-live")
        except Exception as e:
            logger.error("CSAT query error: %s", e)
            return empty

        positive = 0
        negative = 0

        for row in feedback_data:
            try:
                fb = row[0]
                if isinstance(fb, dict):
                    if fb.get("helpful") is True or fb.get("value") == "positive":
                        positive += 1
                    elif fb.get("helpful") is False or fb.get("value") == "negative":
                        negative += 1
                elif isinstance(fb, str):
                    try:
                        parsed = _json.loads(fb)
                        if isinstance(parsed, dict):
                            if parsed.get("helpful") is True or parsed.get("value") == "positive":
                                positive += 1
                            elif parsed.get("helpful") is False or parsed.get("value") == "negative":
                                negative += 1
                        elif isinstance(parsed, bool):
                            if parsed:
                                positive += 1
                            else:
                                negative += 1
                        elif isinstance(parsed, str):
                            if parsed in ["positive", "helpful", "true", "1"]:
                                positive += 1
                            elif parsed in ["negative", "not_helpful", "false", "0"]:
                                negative += 1
                    except Exception:
                        if fb in ("positive", "helpful", "1", "true"):
                            positive += 1
                        elif fb in ("negative", "not_helpful", "0", "false"):
                            negative += 1
            except Exception as e:
                logger.warning("CSAT parse error: %s", e)
                continue

        total_feedback = positive + negative
        csat = round(positive / total_feedback * 100, 1) if total_feedback > 0 else None
        logger.info(
            "CSAT: positive=%d negative=%d total=%d score=%s",
            positive, negative, total_feedback, csat,
        )
        return {
            "csat_score": csat,
            "csat_positive": positive,
            "csat_negative": negative,
            "total_feedback": total_feedback,
        }


    def get_resolution_time_by_category(self, historical_only: bool = False) -> list:
        """Average pipeline execution time per category."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        from sqlalchemy import text as _text

        hist_filter = "AND is_historical = TRUE" if historical_only else "AND (is_historical = FALSE OR is_historical IS NULL)"

        try:
            with self.SessionLocal() as session:
                rows = session.execute(_text(f"""
                    SELECT
                        category,
                        COUNT(*) AS ticket_count,
                        AVG(execution_time_ms) AS avg_time_ms,
                        MIN(execution_time_ms) AS min_time_ms,
                        MAX(execution_time_ms) AS max_time_ms,
                        AVG(CASE WHEN escalation_required = TRUE THEN execution_time_ms END) AS avg_escalated_ms,
                        AVG(CASE WHEN escalation_required = FALSE THEN execution_time_ms END) AS avg_resolved_ms
                    FROM support_tickets
                    WHERE execution_time_ms IS NOT NULL
                      AND execution_time_ms > 0
                      AND category IS NOT NULL
                      AND category != ''
                      {hist_filter}
                    GROUP BY category
                    ORDER BY avg_time_ms DESC
                """)).fetchall()

            return [
                {
                    "category": r[0],
                    "ticket_count": r[1],
                    "avg_time_sec": round((r[2] or 0) / 1000, 1),
                    "min_time_sec": round((r[3] or 0) / 1000, 1),
                    "max_time_sec": round((r[4] or 0) / 1000, 1),
                    "avg_escalated_sec": round((r[5] or 0) / 1000, 1) if r[5] else None,
                    "avg_resolved_sec": round((r[6] or 0) / 1000, 1) if r[6] else None,
                }
                for r in rows
            ]
        except Exception as e:
            logger.error("Resolution time query error: %s", e)
            return []

    def get_cost_forecast(self, historical_only: bool = False) -> dict:
        """Cost forecasting based on ticket volume and per-agent cost assumptions."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return {}
        from sqlalchemy import text as _text

        is_postgres = DATABASE_URL.startswith("postgresql")
        interval_expr = (
            "NOW() - INTERVAL '7 days'" if is_postgres else "datetime('now', '-7 days')"
        )
        hist_filter = "AND is_historical = TRUE" if historical_only else "AND (is_historical = FALSE OR is_historical IS NULL)"

        try:
            with self.SessionLocal() as session:
                daily_volume = session.execute(_text(f"""
                    SELECT DATE(created_at) AS day, COUNT(*) AS tickets
                    FROM support_tickets
                    WHERE created_at >= {interval_expr}
                      {hist_filter}
                    GROUP BY DATE(created_at)
                    ORDER BY day DESC
                """)).fetchall()

                category_costs = session.execute(_text(f"""
                    SELECT
                        t.category,
                        COUNT(*) AS tickets,
                        AVG(
                            COALESCE(
                                (SELECT SUM(oe.cost_usd)
                                 FROM observability_events oe
                                 WHERE oe.reference_id = t.reference_id),
                                0.0031
                            )
                        ) AS avg_cost_usd
                    FROM support_tickets t
                    WHERE t.category IS NOT NULL AND t.category != ''
                      {hist_filter}
                    GROUP BY t.category
                    ORDER BY avg_cost_usd DESC
                """)).fetchall()

        except Exception as e:
            logger.error("Cost forecast query error: %s", e)
            return {}

        base_cost_per_ticket = 0.0031
        total_7days = sum(r[1] for r in daily_volume)
        avg_daily = round(total_7days / 7, 1) if daily_volume else 0

        category_data = []
        for r in category_costs:
            cost = float(r[2]) if r[2] else base_cost_per_ticket
            category_data.append({
                "category": r[0],
                "tickets": r[1],
                "avg_cost_usd": round(cost, 6),
                "monthly_projection_usd": round(cost * avg_daily * 30, 4),
            })

        return {
            "avg_daily_tickets": avg_daily,
            "cost_per_ticket_usd": base_cost_per_ticket,
            "projections": {
                "daily_usd": round(avg_daily * base_cost_per_ticket, 4),
                "weekly_usd": round(avg_daily * 7 * base_cost_per_ticket, 4),
                "monthly_usd": round(avg_daily * 30 * base_cost_per_ticket, 4),
                "yearly_usd": round(avg_daily * 365 * base_cost_per_ticket, 4),
            },
            "by_category": category_data,
            "daily_volume": [{"day": str(r[0]), "tickets": r[1]} for r in daily_volume],
            "assumptions": {
                "classification_cost": "$0.0002/ticket",
                "sentiment_cost": "$0.0003/ticket",
                "response_cost": "$0.0012/ticket",
                "quality_eval_cost": "$0.0012/ticket (Sonnet)",
                "summary_cost": "$0.0002/ticket",
                "total_base": "$0.0031/ticket",
            },
        }


    def cleanup_expired_sessions(self) -> int:
        """Delete guest tickets older than 24 hours. Keeps historical rows."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return 0
        from sqlalchemy import text as _text

        is_postgres = DATABASE_URL.startswith("postgresql")
        interval_expr = "NOW() - INTERVAL '24 hours'" if is_postgres else "datetime('now', '-24 hours')"

        try:
            with self.SessionLocal() as session:
                result = session.execute(_text(f"""
                    DELETE FROM support_tickets
                    WHERE user_id LIKE 'guest-%'
                      AND (is_historical = FALSE OR is_historical IS NULL)
                      AND created_at < {interval_expr}
                """))
                session.commit()
                deleted = result.rowcount or 0
            if deleted > 0:
                logger.info("Session cleanup: deleted %d expired guest tickets", deleted)
            else:
                logger.info("Session cleanup: nothing to delete")
            return deleted
        except Exception as e:
            logger.error("Session cleanup error: %s", e)
            return 0

    def get_ticket_timeline(
        self,
        days: int = 30,
        historical_only: bool = False,
        user_id: str = None,
    ) -> list:
        """Returns ticket count per day for last N days, with zeros for empty days."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        from sqlalchemy import text as _text
        from datetime import timedelta

        if historical_only:
            filter_clause = "AND is_historical = TRUE"
        elif user_id:
            filter_clause = f"AND user_id = '{user_id}' AND (is_historical = FALSE OR is_historical IS NULL)"
        else:
            filter_clause = "AND (is_historical = FALSE OR is_historical IS NULL)"

        is_postgres = DATABASE_URL.startswith("postgresql")
        interval_expr = f"NOW() - INTERVAL '{days} days'" if is_postgres else f"datetime('now', '-{days} days')"

        try:
            with self.SessionLocal() as session:
                rows = session.execute(_text(f"""
                    SELECT DATE(created_at) AS day, COUNT(*) AS count
                    FROM support_tickets
                    WHERE created_at >= {interval_expr}
                      {filter_clause}
                    GROUP BY DATE(created_at)
                    ORDER BY day ASC
                """)).fetchall()
        except Exception as e:
            logger.error("Timeline query error: %s", e)
            return []

        data_map = {str(r[0]): r[1] for r in rows}

        today = datetime.utcnow().date()
        result = []
        for i in range(days - 1, -1, -1):
            day = today - timedelta(days=i)
            day_str = str(day)
            result.append({"date": day_str, "count": data_map.get(day_str, 0)})
        return result

    def get_tickets_filtered(
        self,
        days: int = 30,
        historical_only: bool = False,
        user_id: str = None,
    ) -> List["SupportTicketData"]:
        """Return SupportTicketData filtered by date range and dataset mode."""
        if not self.use_database or not SQLALCHEMY_AVAILABLE:
            return []
        from datetime import timedelta

        try:
            with self.SessionLocal() as session:
                q = session.query(SupportTicketDB)

                if historical_only:
                    q = q.filter(SupportTicketDB.is_historical == True)  # noqa: E712
                else:
                    q = q.filter(
                        (SupportTicketDB.is_historical == False) | (SupportTicketDB.is_historical == None)  # noqa: E711
                    )
                    if user_id:
                        q = q.filter(SupportTicketDB.user_id == user_id)

                if days and days > 0:
                    cutoff = datetime.utcnow() - timedelta(days=days)
                    q = q.filter(SupportTicketDB.created_at >= cutoff)

                db_tickets = q.order_by(SupportTicketDB.created_at.desc()).all()
                return [self._db_to_pydantic(t) for t in db_tickets]
        except Exception as e:
            logger.error("get_tickets_filtered error: %s", e)
            return []


# Global data store instance
data_store = DataStore()