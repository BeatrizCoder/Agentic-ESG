from crewai import Agent, Flow
from crewai.flow.flow import start, listen
from crewai.tools import BaseTool
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import yaml
import random
import unicodedata
from typing import List, Dict, Any
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Load configuration
with open("config/agents.yaml", "r") as f:
    agents_config = yaml.safe_load(f)

with open("config/tasks.yaml", "r") as f:
    tasks_config = yaml.safe_load(f)

# Constants for tools
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
    "angry", "upset", "frustrated", "disappointed", "unhappy", "mad", "annoyed",
    "worried", "concerned", "not happy", "terrible",
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

class ClassificationTool(BaseTool):
    name: str = "Classification Tool"
    description: str = "Classifies customer inquiries into support categories"

    def _run(self, inquiry: str) -> dict[str, Any]:
        """Classify inquiry using keyword matching"""
        inquiry_lower = inquiry.lower()
        scores = {cat: sum(word in inquiry_lower for word in keywords)
                 for cat, keywords in CATEGORY_KEYWORDS.items()}
        best = max(scores, key=scores.get)
        count = scores[best]
        confidence = min(95, 40 + count * 15)
        if best == "General Support" and count == 0:
            confidence = 55

        return {
            "category": best,
            "confidence": confidence,
            "scores": scores
        }


class SentimentTool(BaseTool):
    name: str = "Sentiment Analysis Tool"
    description: str = "Analyzes sentiment and urgency in customer messages"

    def _run(self, inquiry: str) -> dict[str, Any]:
        """Analyze sentiment using keyword matching"""
        inquiry_lower = inquiry.lower()
        found_negative = any(term in inquiry_lower for term in SENTIMENT_NEGATIVE)
        found_urgent = any(term in inquiry_lower for term in SENTIMENT_URGENT)

        if found_negative:
            label = "Concerned"
            confidence = 80
        elif found_urgent:
            label = "Urgent"
            confidence = 70
        else:
            label = "Neutral"
            confidence = 65

        urgency = "High" if found_urgent else "Medium" if found_negative else "Low"

        return {
            "sentiment": label,
            "confidence": confidence,
            "urgency": urgency,
            "found_negative": found_negative,
            "found_urgent": found_urgent
        }


class KnowledgeTool(BaseTool):
    name: str = "Knowledge Retrieval Tool"
    description: str = "Retrieves knowledge base articles for support categories"

    def _run(self, category: str) -> dict[str, Any]:
        """Retrieve relevant articles for a category"""
        articles = KNOWLEDGE_BASE.get(category, KNOWLEDGE_BASE["General Support"])

        return {
            "articles": articles,
            "count": len(articles),
            "category": category
        }


class ResponseTool(BaseTool):
    name: str = "Response Generation Tool"
    description: str = "Generates appropriate customer responses based on context"

    def _run(self, category: str, urgency: str, articles_count: int) -> dict[str, Any]:
        """Generate appropriate response based on context"""
        template = RESPONSE_TEMPLATES.get(category, RESPONSE_TEMPLATES["General Support"])
        response = template
        if urgency == "High":
            response += " I have flagged this as a priority, and our support team will respond as soon as possible."

        confidence = 60
        if category != "General Support":
            confidence += 15
        if urgency == "Low":
            confidence += 5
        if articles_count >= 2:
            confidence += 10

        return {
            "response": response,
            "confidence": min(95, confidence),
            "template_used": category
        }


class EscalationTool(BaseTool):
    name: str = "Escalation Evaluation Tool"
    description: str = "Evaluates if cases need escalation to human support"

    def _run(self, response_confidence: int, sentiment: str, articles_count: int, inquiry: str) -> dict[str, Any]:
        """Evaluate if case needs escalation"""
        escalate = False
        reason = "Sufficient confidence in automated response."
        triggered_keyword = None

        # Check for explicit escalation keywords in the inquiry (multilingual)
        normalized_inquiry = normalize_text(inquiry)

        # Combine all keywords from both languages
        all_keywords = ESCALATION_KEYWORDS["en"] + ESCALATION_KEYWORDS["pt"]

        for keyword in all_keywords:
            normalized_keyword = normalize_text(keyword)
            if normalized_keyword in normalized_inquiry:
                escalate = True
                triggered_keyword = keyword
                reason = f"User explicitly requested escalation or human support (keyword: '{keyword}')."
                break

        if not escalate:
            if response_confidence < 55:
                escalate = True
                reason = "Low confidence in automated response."
            elif sentiment == "Concerned" and response_confidence < 70:
                escalate = True
                reason = "Sensitive issue with low confidence."
            elif articles_count == 0:
                escalate = True
                reason = "Insufficient knowledge base support."

        reference_id = f"ESC-2026-{random.randint(1000, 9999)}" if escalate else ""

        return {
            "escalation_required": escalate,
            "reason": reason,
            "reference_id": reference_id,
            "triggered_keyword": triggered_keyword
        }


class SupportTicket(BaseModel):
    inquiry: str


class SupportResponse(BaseModel):
    inquiry: str
    category: str
    category_confidence: int
    sentiment: str
    sentiment_confidence: int
    urgency: str
    articles: list[str]
    response: str
    response_confidence: int
    escalation_required: bool
    escalation_reason: str
    reference_id: str
    triggered_keyword: str | None = None
    steps: list[dict[str, Any]]


class SupportState(BaseModel):
    inquiry: str = ""
    category: str = "General Support"
    category_confidence: int = 0
    sentiment: str = "Neutral"
    sentiment_confidence: int = 0
    urgency: str = "Low"
    articles: list[str] = []
    response: str = ""
    response_confidence: int = 0
    escalation_required: bool = False
    escalation_reason: str = ""
    reference_id: str = ""
    triggered_keyword: str | None = None
    steps: list[dict[str, Any]] = []

    def log_step(self, agent_name: str, details: dict[str, Any]) -> None:
        self.steps.append({"agent": agent_name, "details": details})


class SupportCrew:
    def __init__(self):
        self.agents = {}
        self.steps: list[dict[str, Any]] = []
        self._create_agents()

    def _create_agents(self):
        """Create agents from configuration with tools"""
        for agent_name, config in agents_config.items():
            # Add tools based on agent role
            tools = []
            if agent_name == "classifier_agent":
                tools.append(ClassificationTool())
            elif agent_name == "sentiment_agent":
                tools.append(SentimentTool())
            elif agent_name == "knowledge_agent":
                tools.append(KnowledgeTool())
            elif agent_name == "response_agent":
                tools.append(ResponseTool())
            elif agent_name == "escalation_agent":
                tools.append(EscalationTool())

            self.agents[agent_name] = Agent(
                role=config["role"],
                goal=config["goal"],
                backstory=config["backstory"],
                tools=tools,
                verbose=True
            )

    def log_step(self, agent_name: str, details: dict[str, Any]) -> None:
        self.steps.append({"agent": agent_name, "details": details})

    def execute_tool(self, agent_key: str, *args: Any, **kwargs: Any) -> dict[str, Any]:
        agent = self.agents[agent_key]
        tool = agent.tools[0]
        result = tool._run(*args, **kwargs)
        self.log_step(agent.role, {
            "tool_used": tool.name,
            "input": args,
            "kwargs": kwargs,
            "output": result,
        })
        return result

    def ask_agent(self, from_agent: str, to_agent: str, question: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        self.log_step(from_agent, {
            "collaboration": "ask",
            "target_agent": to_agent,
            "question": question,
            "context": context,
        })
        response = f"{to_agent} acknowledged the question: {question}"
        self.log_step(to_agent, {
            "collaboration": "respond",
            "from_agent": from_agent,
            "response": response,
        })
        return response

    def delegate_task(self, from_agent: str, to_agent: str, task_description: str, context: dict[str, Any] | None = None) -> str:
        context = context or {}
        self.log_step(from_agent, {
            "collaboration": "delegate",
            "target_agent": to_agent,
            "task": task_description,
            "context": context,
        })
        result = f"{to_agent} completed task: {task_description}"
        self.log_step(to_agent, {
            "collaboration": "task_completed",
            "from_agent": from_agent,
            "result": result,
        })
        return result

    def process_support_request(self, inquiry: str) -> Dict[str, Any]:
        """Process a support request using tools and agent orchestration"""
        self.steps = []

        classification_result = self.execute_tool("classifier_agent", inquiry)
        sentiment_result = self.execute_tool("sentiment_agent", inquiry)
        knowledge_result = self.execute_tool("knowledge_agent", classification_result["category"])

        self.ask_agent(
            "Response Generation Agent",
            "Knowledge Retrieval Agent",
            f"What articles are available for category '{classification_result['category']}'?",
            {"current_category": classification_result["category"]},
        )

        response_result = self.execute_tool(
            "response_agent",
            classification_result["category"],
            sentiment_result["urgency"],
            knowledge_result["count"],
        )

        self.delegate_task(
            "Escalation Agent",
            "Sentiment Analysis Agent",
            "Review response confidence and sentiment for escalation decision",
            {
                "response_confidence": response_result["confidence"],
                "sentiment": sentiment_result["sentiment"],
            },
        )

        escalation_result = self.execute_tool(
            "escalation_agent",
            response_result["confidence"],
            sentiment_result["sentiment"],
            knowledge_result["count"],
        )

        return {
            "category": classification_result["category"],
            "category_confidence": classification_result["confidence"],
            "sentiment": sentiment_result["sentiment"],
            "sentiment_confidence": sentiment_result["confidence"],
            "urgency": sentiment_result["urgency"],
            "articles": knowledge_result["articles"],
            "response": response_result["response"],
            "response_confidence": response_result["confidence"],
            "escalation_required": escalation_result["escalation_required"],
            "escalation_reason": escalation_result["reason"],
            "reference_id": escalation_result["reference_id"],
            "steps": self.steps,
        }





class SupportFlow(Flow[SupportState]):
    def __init__(self, crew: SupportCrew):
        super().__init__()
        self.crew = crew

    @start()
    def classify_inquiry(self):
        self.crew.steps = []
        result = self.crew.execute_tool("classifier_agent", self.state.inquiry)
        self.state.category = result["category"]
        self.state.category_confidence = result["confidence"]
        return f"Classified inquiry as {self.state.category}"

    @listen(classify_inquiry)
    def analyze_sentiment(self):
        result = self.crew.execute_tool("sentiment_agent", self.state.inquiry)
        self.state.sentiment = result["sentiment"]
        self.state.sentiment_confidence = result["confidence"]
        self.state.urgency = result["urgency"]
        return f"Analyzed sentiment as {self.state.sentiment}"

    @listen(analyze_sentiment)
    def retrieve_knowledge(self):
        result = self.crew.execute_tool("knowledge_agent", self.state.category)
        self.state.articles = result["articles"]
        return f"Retrieved {len(self.state.articles)} knowledge articles"

    @listen(retrieve_knowledge)
    def generate_response(self):
        self.crew.ask_agent(
            "Response Generation Agent",
            "Knowledge Retrieval Agent",
            f"What articles are available for category '{self.state.category}'?",
            {"current_category": self.state.category},
        )

        result = self.crew.execute_tool(
            "response_agent",
            self.state.category,
            self.state.urgency,
            len(self.state.articles),
        )
        self.state.response = result["response"]
        self.state.response_confidence = result["confidence"]
        return f"Generated response with confidence {self.state.response_confidence}%"

    @listen(generate_response)
    def evaluate_escalation(self):
        self.crew.delegate_task(
            "Escalation Agent",
            "Sentiment Analysis Agent",
            "Review response confidence and sentiment for escalation decision",
            {
                "response_confidence": self.state.response_confidence,
                "sentiment": self.state.sentiment,
            },
        )

        result = self.crew.execute_tool(
            "escalation_agent",
            self.state.response_confidence,
            self.state.sentiment,
            len(self.state.articles),
            self.state.inquiry,
        )
        self.state.escalation_required = result["escalation_required"]
        self.state.escalation_reason = result["reason"]
        self.state.reference_id = result["reference_id"]
        self.state.triggered_keyword = result.get("triggered_keyword")

        # Update response if escalation is required
        if self.state.escalation_required:
            self.state.response += (
                "\n\nYour inquiry has been flagged for human review. "
                "A support agent will contact you within 24 hours to assist you further."
            )
            if self.state.reference_id:
                self.state.response += f"\n\nReference ID: {self.state.reference_id}"

        self.state.steps = self.crew.steps
        return f"Escalation {'required' if self.state.escalation_required else 'not required'}"


app = FastAPI(
    title="AAMAD Support Backend",
    description="Backend API for the CrewAI multi-agent support interface.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

support_crew = SupportCrew()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aamad backend"}


@app.post("/api/support", response_model=SupportResponse)
async def create_support_ticket(ticket: SupportTicket) -> SupportResponse:
    inquiry = ticket.inquiry.strip()
    if not inquiry:
        raise HTTPException(status_code=400, detail="Inquiry text cannot be empty.")

    # Process the support request through the CrewAI flow
    support_flow = SupportFlow(SupportCrew())
    await support_flow.kickoff_async({"inquiry": inquiry})
    final_state = support_flow.state

    # Build response model with the same fields
    response = SupportResponse(
        inquiry=inquiry,
        category=final_state.category,
        category_confidence=final_state.category_confidence,
        sentiment=final_state.sentiment,
        sentiment_confidence=final_state.sentiment_confidence,
        urgency=final_state.urgency,
        articles=final_state.articles,
        response=final_state.response,
        response_confidence=final_state.response_confidence,
        escalation_required=final_state.escalation_required,
        escalation_reason=final_state.escalation_reason,
        reference_id=final_state.reference_id,
        triggered_keyword=final_state.triggered_keyword,
        steps=final_state.steps,
    )

    return response


def main(argv: list[str] | None = None) -> int:
    import uvicorn

    uvicorn.run(
        "aamad.backend:app",
        host="0.0.0.0",
        port=8000,
        log_level="info",
        reload=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
