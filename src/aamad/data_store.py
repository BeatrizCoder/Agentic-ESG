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
    feedback: Optional[Dict[str, Any]] = None
    run_id: Optional[str] = None
    execution_time_ms: int = 0
    wall_time_sec: Optional[float] = None
    token_usage: Dict[str, Any] = {}
    cost_usd: float = 0.0
    api_tags: List[str] = []
    quality_evaluation: Dict[str, Any] = {}


class DataStore:
    """Abstract data store supporting both JSON and PostgreSQL backends."""

    def __init__(self, data_dir: str = "src/aamad/data"):
        self.data_dir = data_dir
        self.tickets_file = os.path.join(data_dir, "tickets.json")
        self.use_database = DATABASE_PROVIDER.lower() in ("postgres", "sqlite") and SQLALCHEMY_AVAILABLE

        if self.use_database:
            self.engine = create_engine(DATABASE_URL)
            self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
            Base.metadata.create_all(bind=self.engine)
            self._migrate_add_api_tags()
            self._seed_refunds()
            logger.info("Using %s database for data storage", DATABASE_PROVIDER)
        else:
            os.makedirs(data_dir, exist_ok=True)
            self._ensure_data_file()
            logger.info("Using JSON file storage for data persistence")

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

    def get_all_tickets(self) -> List[SupportTicketData]:
        """Get all support tickets."""
        if self.use_database:
            db = self.SessionLocal()
            try:
                db_tickets = db.query(SupportTicketDB).all()
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


# Global data store instance
data_store = DataStore()