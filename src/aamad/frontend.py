"""
Multi-Agent Customer Support Crew — Frontend v2.0
Enterprise SaaS UI redesign with Customer View + Operator View separation.
"""

from __future__ import annotations

import json
import time
import random
import uuid
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Any

import requests
import streamlit as st

# ─────────────────────────────────────────────
# CONSTANTS
# ─────────────────────────────────────────────

DEFAULT_BACKEND_URL = "http://127.0.0.1:8000/api/support"

AGENT_META = {
    "Classification Tool":         {"icon": "⬡", "label": "Classifier",          "color": "#6EE7B7"},
    "Sentiment Analysis Tool":     {"icon": "◈", "label": "Sentiment",            "color": "#93C5FD"},
    "Knowledge Retrieval Tool":    {"icon": "⬡", "label": "Knowledge",            "color": "#FCD34D"},
    "Response Generation Tool":    {"icon": "◈", "label": "Response Gen",         "color": "#C4B5FD"},
    "Escalation Evaluation Tool":  {"icon": "⬡", "label": "Escalation",           "color": "#FCA5A5"},
    "Memory Management Tool":      {"icon": "◈", "label": "Memory",               "color": "#6EE7B7"},
}

CATEGORY_ICONS = {
    "Order Issues":     "📦",
    "Billing":          "💳",
    "Account Access":   "🔐",
    "Technical Issue":  "⚙️",
    "General Support":  "💬",
}

SENTIMENT_CONFIG = {
    "Neutral":   {"color": "#6EE7B7", "bg": "rgba(110,231,183,0.12)", "label": "Neutral"},
    "Concerned": {"color": "#FCA5A5", "bg": "rgba(252,165,165,0.12)", "label": "Concerned"},
    "Urgent":    {"color": "#FCD34D", "bg": "rgba(252,211,77,0.12)",  "label": "Urgent"},
}

URGENCY_CONFIG = {
    "Low":    {"color": "#6EE7B7", "dot": "🟢"},
    "Medium": {"color": "#FCD34D", "dot": "🟡"},
    "High":   {"color": "#FCA5A5", "dot": "🔴"},
}

# Agents list for progress tracking
AGENTS = [
    {"emoji": "⬡", "name": "Classifier Agent"},
    {"emoji": "◈", "name": "Sentiment Agent"},
    {"emoji": "⬡", "name": "Knowledge Agent"},
    {"emoji": "◈", "name": "Response Generation Agent"},
    {"emoji": "⬡", "name": "Escalation Agent"},
]

# ─────────────────────────────────────────────
# DATA MODELS
# ─────────────────────────────────────────────

@dataclass
class TicketResult:
    """Result of ticket analysis."""
    inquiry: str
    category: str = "General Support"
    category_confidence: float = 0.0
    sentiment_label: str = "Neutral"
    sentiment_confidence: float = 0.0
    urgency: str = "Low"
    articles: list[str] = field(default_factory=list)
    response: str = ""
    response_confidence: float = 0.0
    escalation_required: bool = False
    escalation_reason: str = ""
    reference_id: str = ""
    triggered_keyword: str | None = None
    timestamp: datetime = field(default_factory=datetime.now)


def analyze_ticket(inquiry: str) -> TicketResult:
    """Analyze a support ticket inquiry locally (fallback for backend unavailability)."""
    ref_id = str(uuid.uuid4())[:12]
    
    # Simple keyword-based classification
    inquiry_lower = inquiry.lower()
    
    categories = {
        "Order Issues": ["order", "delivery", "package", "shipment", "tracking"],
        "Billing": ["charge", "payment", "invoice", "bill", "refund", "money"],
        "Account Access": ["password", "login", "access", "account", "locked", "reset"],
        "Technical Issue": ["error", "bug", "crash", "slow", "broken", "issue"],
    }
    
    category = "General Support"
    for cat, keywords in categories.items():
        if any(kw in inquiry_lower for kw in keywords):
            category = cat
            break
    
    # Sentiment analysis based on keywords
    sentiment = "Neutral"
    urgency = "Low"
    
    if any(word in inquiry_lower for word in ["urgent", "asap", "emergency", "immediately", "critical"]):
        urgency = "High"
        sentiment = "Urgent"
    elif any(word in inquiry_lower for word in ["disappointed", "angry", "frustrated", "upset", "problem"]):
        sentiment = "Concerned"
        urgency = "Medium"
    
    # Generate a basic response
    response = (
        f"Thank you for reaching out regarding your {category.lower()}. "
        f"We appreciate your inquiry and will process it promptly. "
        f"Our team is working to resolve this for you."
    )
    
    escalation_required = urgency == "High" or sentiment == "Urgent"
    escalation_reason = "High urgency detected" if escalation_required else ""
    
    return TicketResult(
        inquiry=inquiry,
        category=category,
        category_confidence=0.75,
        sentiment_label=sentiment,
        sentiment_confidence=0.70,
        urgency=urgency,
        articles=[],
        response=response,
        response_confidence=0.65,
        escalation_required=escalation_required,
        escalation_reason=escalation_reason,
        reference_id=ref_id,
        triggered_keyword=None,
        timestamp=datetime.now(),
    )

# ─────────────────────────────────────────────
# PAGE CONFIG
# ─────────────────────────────────────────────

st.set_page_config(
    page_title="SupportAI — Multi-Agent Platform",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────
# GLOBAL CSS
# ─────────────────────────────────────────────

def inject_css() -> None:
    st.markdown("""
    <style>
    /* ── FONTS ── */
    @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Sora:wght@300;400;500;600;700&display=swap');

    /* ── RESET & ROOT ── */
    :root {
        --bg:          #0B0F1A;
        --surface:     #111827;
        --surface2:    #1A2233;
        --border:      rgba(255,255,255,0.07);
        --border-h:    rgba(255,255,255,0.14);
        --text:        #E2E8F0;
        --text-muted:  #64748B;
        --accent:      #38BDF8;
        --accent2:     #6EE7B7;
        --danger:      #FCA5A5;
        --warn:        #FCD34D;
        --radius:      12px;
        --radius-sm:   8px;
        --font:        'Sora', sans-serif;
        --mono:        'DM Mono', monospace;
        --shadow:      0 4px 24px rgba(0,0,0,0.4);
    }

    html, body, [class*="css"] {
        font-family: var(--font) !important;
        background-color: var(--bg) !important;
        color: var(--text) !important;
    }

    /* ── STREAMLIT CHROME ── */
    #MainMenu, footer, header { visibility: hidden; }
    .block-container {
        padding: 0 2rem 3rem 2rem !important;
        max-width: 1400px !important;
    }

    /* ── SIDEBAR ── */
    section[data-testid="stSidebar"] {
        background: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
        padding-top: 0 !important;
    }
    section[data-testid="stSidebar"] > div {
        padding-top: 0 !important;
    }
    .sidebar-logo {
        display: flex;
        align-items: center;
        gap: 10px;
        padding: 24px 20px 20px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 8px;
    }
    .sidebar-logo-icon {
        width: 36px; height: 36px;
        background: linear-gradient(135deg, #38BDF8, #6EE7B7);
        border-radius: 8px;
        display: flex; align-items: center; justify-content: center;
        font-size: 18px;
        flex-shrink: 0;
    }
    .sidebar-logo-text { font-size: 15px; font-weight: 700; letter-spacing: -0.3px; }
    .sidebar-logo-sub  { font-size: 11px; color: var(--text-muted); margin-top: 1px; }

    .sidebar-section-label {
        font-size: 10px; font-weight: 600; letter-spacing: 1.4px;
        color: var(--text-muted); text-transform: uppercase;
        padding: 16px 20px 6px;
    }

    /* ── NAV RADIO OVERRIDES ── */
    div[data-testid="stRadio"] label {
        display: flex !important;
        align-items: center !important;
        gap: 10px !important;
        padding: 10px 16px !important;
        border-radius: var(--radius-sm) !important;
        cursor: pointer !important;
        transition: background 0.15s !important;
        font-size: 14px !important;
        color: var(--text-muted) !important;
        font-weight: 500 !important;
        margin: 2px 4px !important;
    }
    div[data-testid="stRadio"] label:hover {
        background: rgba(56,189,248,0.08) !important;
        color: var(--text) !important;
    }
    div[data-testid="stRadio"] [data-checked="true"] + label,
    div[data-testid="stRadio"] input:checked + div label {
        background: rgba(56,189,248,0.12) !important;
        color: var(--accent) !important;
    }
    div[data-testid="stRadio"] > div { gap: 0 !important; }
    div[data-testid="stRadio"] [data-testid="stMarkdownContainer"] p { margin: 0 !important; }

    /* ── BUTTONS ── */
    .stButton > button {
        font-family: var(--font) !important;
        font-weight: 600 !important;
        font-size: 14px !important;
        border-radius: var(--radius-sm) !important;
        border: none !important;
        cursor: pointer !important;
        transition: all 0.2s !important;
        letter-spacing: 0.2px !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #38BDF8, #0EA5E9) !important;
        color: #0B0F1A !important;
        padding: 10px 24px !important;
    }
    .stButton > button[kind="primary"]:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 20px rgba(56,189,248,0.4) !important;
    }
    .stButton > button[kind="secondary"] {
        background: var(--surface2) !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
    }
    .stButton > button[kind="secondary"]:hover {
        border-color: var(--border-h) !important;
        background: rgba(255,255,255,0.05) !important;
    }

    /* ── TEXT INPUT ── */
    .stTextArea textarea, .stTextInput input {
        font-family: var(--font) !important;
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text) !important;
        font-size: 14px !important;
        transition: border-color 0.2s !important;
    }
    .stTextArea textarea:focus, .stTextInput input:focus {
        border-color: var(--accent) !important;
        box-shadow: 0 0 0 3px rgba(56,189,248,0.12) !important;
    }
    .stTextArea textarea::placeholder, .stTextInput input::placeholder {
        color: var(--text-muted) !important;
    }

    /* ── SELECTBOX / RADIO ── */
    .stSelectbox select {
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text) !important;
    }

    /* ── SPINNER ── */
    .stSpinner > div { border-color: var(--accent) transparent transparent !important; }

    /* ── CARDS ── */
    .card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 24px;
        margin-bottom: 16px;
        transition: border-color 0.2s;
    }
    .card:hover { border-color: var(--border-h); }
    .card-sm {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 16px;
    }
    .card-accent {
        background: linear-gradient(135deg, rgba(56,189,248,0.06), rgba(110,231,183,0.04));
        border: 1px solid rgba(56,189,248,0.2);
        border-radius: var(--radius);
        padding: 24px;
    }
    .card-danger {
        background: rgba(252,165,165,0.06);
        border: 1px solid rgba(252,165,165,0.25);
        border-radius: var(--radius);
        padding: 24px;
    }

    /* ── TOP NAVBAR ── */
    .top-nav {
        display: flex; align-items: center; justify-content: space-between;
        padding: 20px 0 24px;
        border-bottom: 1px solid var(--border);
        margin-bottom: 28px;
    }
    .top-nav-title { font-size: 22px; font-weight: 700; letter-spacing: -0.5px; }
    .top-nav-sub   { font-size: 13px; color: var(--text-muted); margin-top: 2px; }

    /* ── STATUS PILLS ── */
    .pill {
        display: inline-flex; align-items: center; gap: 5px;
        font-size: 11px; font-weight: 600; letter-spacing: 0.5px;
        padding: 3px 10px; border-radius: 999px;
        font-family: var(--mono);
        text-transform: uppercase;
    }
    .pill-green  { background: rgba(110,231,183,0.15); color: #6EE7B7; border: 1px solid rgba(110,231,183,0.3); }
    .pill-red    { background: rgba(252,165,165,0.15); color: #FCA5A5; border: 1px solid rgba(252,165,165,0.3); }
    .pill-yellow { background: rgba(252,211,77,0.15);  color: #FCD34D; border: 1px solid rgba(252,211,77,0.3);  }
    .pill-blue   { background: rgba(56,189,248,0.15);  color: #38BDF8; border: 1px solid rgba(56,189,248,0.3);  }
    .pill-gray   { background: rgba(100,116,139,0.15); color: #94A3B8; border: 1px solid rgba(100,116,139,0.3); }

    /* ── BADGE ── */
    .badge {
        display: inline-block;
        font-size: 11px; font-weight: 700;
        padding: 2px 8px; border-radius: 4px;
        background: rgba(56,189,248,0.15); color: var(--accent);
        font-family: var(--mono);
    }

    /* ── METRIC CARD ── */
    .metric-card {
        background: var(--surface);
        border: 1px solid var(--border);
        border-radius: var(--radius);
        padding: 20px;
        text-align: center;
    }
    .metric-value {
        font-size: 32px; font-weight: 700; letter-spacing: -1px;
        font-family: var(--mono); line-height: 1;
    }
    .metric-label {
        font-size: 11px; color: var(--text-muted); margin-top: 6px;
        font-weight: 600; text-transform: uppercase; letter-spacing: 0.8px;
    }
    .metric-delta { font-size: 12px; margin-top: 4px; }

    /* ── AGENT TIMELINE ── */
    .timeline { position: relative; padding-left: 28px; }
    .timeline::before {
        content: '';
        position: absolute; left: 10px; top: 0; bottom: 0;
        width: 1px; background: var(--border);
    }
    .tl-step {
        position: relative; margin-bottom: 20px;
    }
    .tl-step::before {
        content: '';
        position: absolute; left: -22px; top: 5px;
        width: 8px; height: 8px;
        border-radius: 50%; background: var(--accent);
        box-shadow: 0 0 0 3px rgba(56,189,248,0.2);
    }
    .tl-step.done::before  { background: #6EE7B7; box-shadow: 0 0 0 3px rgba(110,231,183,0.2); }
    .tl-step.error::before { background: #FCA5A5; box-shadow: 0 0 0 3px rgba(252,165,165,0.2); }
    .tl-step.active::before {
        background: var(--accent);
        animation: pulse 1.2s ease-in-out infinite;
    }
    @keyframes pulse {
        0%, 100% { box-shadow: 0 0 0 3px rgba(56,189,248,0.2); }
        50%       { box-shadow: 0 0 0 6px rgba(56,189,248,0.1); }
    }
    .tl-label    { font-size: 13px; font-weight: 600; margin-bottom: 3px; }
    .tl-sub      { font-size: 12px; color: var(--text-muted); font-family: var(--mono); }
    .tl-time     { font-size: 10px; color: var(--text-muted); font-family: var(--mono); margin-top: 2px; }

    /* ── CONFIDENCE BAR ── */
    .conf-bar-wrap {
        background: rgba(255,255,255,0.05);
        border-radius: 999px; height: 6px; overflow: hidden;
        margin-top: 6px;
    }
    .conf-bar {
        height: 100%; border-radius: 999px;
        background: linear-gradient(90deg, #38BDF8, #6EE7B7);
        transition: width 0.6s ease;
    }

    /* ── RESPONSE BUBBLE ── */
    .response-bubble {
        background: var(--surface2);
        border: 1px solid var(--border);
        border-left: 3px solid var(--accent);
        border-radius: var(--radius);
        padding: 20px 22px;
        font-size: 15px;
        line-height: 1.7;
        color: var(--text);
    }
    .escalation-bubble {
        background: rgba(252,165,165,0.05);
        border: 1px solid rgba(252,165,165,0.25);
        border-left: 3px solid #FCA5A5;
        border-radius: var(--radius);
        padding: 20px 22px;
    }

    /* ── TICKET ROW ── */
    .ticket-row {
        display: flex; align-items: center;
        padding: 14px 18px;
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        margin-bottom: 8px;
        background: var(--surface);
        transition: border-color 0.15s;
        gap: 14px;
    }
    .ticket-row:hover { border-color: var(--border-h); }
    .ticket-id   { font-family: var(--mono); font-size: 11px; color: var(--text-muted); min-width: 110px; }
    .ticket-inquiry { font-size: 13px; flex: 1; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ticket-cat  { font-size: 11px; color: var(--text-muted); min-width: 110px; }

    /* ── DIVIDER ── */
    .divider { border: none; border-top: 1px solid var(--border); margin: 20px 0; }

    /* ── SECTION HEADING ── */
    .section-heading {
        font-size: 11px; font-weight: 700; letter-spacing: 1.5px;
        color: var(--text-muted); text-transform: uppercase;
        margin-bottom: 14px;
    }

    /* ── EMPTY STATE ── */
    .empty-state {
        text-align: center; padding: 48px 24px;
        color: var(--text-muted);
    }
    .empty-state-icon { font-size: 36px; margin-bottom: 12px; }
    .empty-state-title { font-size: 16px; font-weight: 600; color: var(--text); margin-bottom: 6px; }
    .empty-state-sub   { font-size: 13px; }

    /* ── ACCORDION DETAILS ── */
    details {
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        padding: 0;
        margin-bottom: 8px;
    }
    details[open] { border-color: var(--border-h); }
    summary {
        font-size: 13px; font-weight: 600;
        padding: 12px 16px; cursor: pointer;
        list-style: none; display: flex; align-items: center; gap: 8px;
        color: var(--text);
    }
    summary::-webkit-details-marker { display: none; }
    summary::after {
        content: '›'; margin-left: auto; color: var(--text-muted);
        transition: transform 0.2s; font-size: 18px;
    }
    details[open] summary::after { transform: rotate(90deg); }
    .details-body { padding: 0 16px 16px; font-size: 12px; font-family: var(--mono); color: var(--text-muted); }

    /* ── STREAMLIT OVERRIDES ── */
    .stProgress > div > div { background: linear-gradient(90deg, #38BDF8, #6EE7B7) !important; }
    .stProgress { background: rgba(255,255,255,0.05) !important; border-radius: 999px !important; }

    div[data-testid="stMetric"] {
        background: var(--surface) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius) !important;
        padding: 16px !important;
    }
    div[data-testid="stMetric"] label { color: var(--text-muted) !important; font-size: 11px !important; text-transform: uppercase !important; letter-spacing: 0.8px !important; }
    div[data-testid="stMetric"] [data-testid="stMetricValue"] { font-family: var(--mono) !important; font-size: 28px !important; font-weight: 700 !important; }

    div[data-testid="stExpander"] {
        background: var(--surface2) !important;
        border: 1px solid var(--border) !important;
        border-radius: var(--radius-sm) !important;
    }
    div[data-testid="stExpander"] summary { font-weight: 600 !important; }

    label[data-testid="stWidgetLabel"] { color: var(--text-muted) !important; font-size: 12px !important; font-weight: 600 !important; text-transform: uppercase !important; letter-spacing: 0.6px !important; }

    div.stAlert {
        background: rgba(56,189,248,0.06) !important;
        border: 1px solid rgba(56,189,248,0.2) !important;
        border-radius: var(--radius-sm) !important;
        color: var(--text) !important;
    }

    /* ── CUSTOMER HERO ── */
    .customer-hero {
        text-align: center;
        padding: 40px 24px 32px;
    }
    .customer-hero-badge {
        display: inline-flex; align-items: center; gap: 6px;
        background: rgba(56,189,248,0.1); border: 1px solid rgba(56,189,248,0.2);
        border-radius: 999px; padding: 5px 14px;
        font-size: 12px; color: var(--accent); font-weight: 600;
        margin-bottom: 18px; letter-spacing: 0.3px;
    }
    .customer-hero-title { font-size: 28px; font-weight: 700; letter-spacing: -0.8px; margin-bottom: 10px; }
    .customer-hero-sub   { font-size: 15px; color: var(--text-muted); max-width: 400px; margin: 0 auto; line-height: 1.6; }

    /* ── LOADING AGENT STEP ── */
    .agent-loading-step {
        display: flex; align-items: center; gap: 12px;
        padding: 10px 14px;
        background: var(--surface2);
        border: 1px solid var(--border);
        border-radius: var(--radius-sm);
        margin-bottom: 8px;
        font-size: 13px;
    }
    .agent-dot-active {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--accent);
        animation: pulse 1.2s ease-in-out infinite;
        flex-shrink: 0;
    }
    .agent-dot-done {
        width: 8px; height: 8px; border-radius: 50%;
        background: #6EE7B7; flex-shrink: 0;
    }
    .agent-dot-wait {
        width: 8px; height: 8px; border-radius: 50%;
        background: var(--border); flex-shrink: 0;
    }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SESSION STATE
# ─────────────────────────────────────────────

def init_state() -> None:
    defaults = {
        "tickets": [],          # list of ticket dicts
        "active_ticket": None,  # currently viewed ticket
        "view": "Customer",     # "Customer" | "Operator"
        "backend_url": DEFAULT_BACKEND_URL,
        "use_backend": True,
        "customer_result": None,
        "processing": False,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v


# ─────────────────────────────────────────────
# API / LOCAL LOGIC
# ─────────────────────────────────────────────

def call_backend(inquiry: str, backend_url: str) -> dict[str, Any]:
    resp = requests.post(
        backend_url,
        json={"inquiry": inquiry},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def local_analyze(inquiry: str) -> dict[str, Any]:
    """Deterministic fallback when no backend is available."""
    import unicodedata, random as rng

    def norm(t): return t.lower().strip()
    cat_kw = {
        "Order Issues":    ["order","tracking","shipment","delivery","package","delay"],
        "Billing":         ["bill","charge","refund","invoice","payment","price"],
        "Account Access":  ["account","login","password","sign","locked","profile"],
        "Technical Issue": ["error","bug","crash","failed","site","website","problem"],
        "General Support": ["question","help","support","information","request"],
    }
    t = norm(inquiry)
    scores = {c: sum(1 for kw in kws if kw in t) for c, kws in cat_kw.items()}
    category = max(scores, key=scores.get)
    conf = min(95, 40 + scores[category] * 15)
    if category == "General Support" and scores[category] == 0: conf = 50

    neg = any(w in t for w in ["angry","upset","frustrated","disappointed","unhappy","worried","terrible"])
    urg = any(w in t for w in ["urgent","asap","immediately","right away"])
    sentiment = "Concerned" if neg else ("Urgent" if urg else "Neutral")
    urgency   = "High" if urg else ("Medium" if neg else "Low")
    s_conf    = 80 if neg else (70 if urg else 65)

    kb = {
        "Order Issues":    ["Order Delivery Delays","Tracking Your Package","Order Status & ETA"],
        "Billing":         ["Refunds and Billing","Understanding Your Invoice","Payment Methods"],
        "Account Access":  ["Resetting Your Password","Recovering a Locked Account","Updating Account Info"],
        "Technical Issue": ["Troubleshooting Login Errors","Site Performance Problems","Clearing Browser Cache"],
        "General Support": ["Contacting Customer Service","Using Our Help Center"],
    }
    articles = kb.get(category, kb["General Support"])

    templates = {
        "Order Issues":    "I'm sorry to hear about the issue with your order. Your shipment may be experiencing a temporary delay — it should arrive within 2-3 business days. I can provide tracking details if needed.",
        "Billing":         "I understand your concern about the billing charge. I can review the payment details or initiate a refund request on your behalf.",
        "Account Access":  "I can help you regain access to your account. Please try resetting your password from the sign-in page. If the account remains locked, our recovery team will assist.",
        "Technical Issue": "Thank you for reporting this issue. I recommend refreshing the page or clearing your browser cache. If the problem persists, our engineering team will be escalated.",
        "General Support": "Thanks for reaching out. I'm happy to help answer your question or point you to the right resource for a quick resolution.",
    }
    response = templates.get(category, templates["General Support"])
    r_conf = min(95, 60 + (15 if category != "General Support" else 0) + (5 if sentiment == "Neutral" else 0) + 10)

    esc_kw = ["escalate","talk to someone","human agent","manager","supervisor","refund","reembolso","gerente"]
    esc_kw_hit = next((kw for kw in esc_kw if kw in t), None)
    if esc_kw_hit:
        esc = True; esc_reason = f"User explicitly requested escalation (keyword: '{esc_kw_hit}')"
    elif r_conf < 55:
        esc = True; esc_reason = "Low confidence in automated response"
    elif sentiment == "Concerned" and r_conf < 70:
        esc = True; esc_reason = "Sensitive issue with low confidence"
    else:
        esc = False; esc_reason = "Sufficient confidence in automated response"

    ref_id = f"ESC-2026-{rng.randint(1000,9999)}" if esc else f"REF-{int(time.time())}"

    steps = [
        {"agent": "Classification Tool",        "details": {"category": category, "confidence": conf}},
        {"agent": "Sentiment Analysis Tool",     "details": {"sentiment": sentiment, "urgency": urgency, "confidence": s_conf}},
        {"agent": "Knowledge Retrieval Tool",    "details": {"articles": articles, "count": len(articles)}},
        {"agent": "Response Generation Tool",    "details": {"confidence": r_conf, "template": category}},
        {"agent": "Escalation Evaluation Tool",  "details": {"escalation_required": esc, "reason": esc_reason}},
    ]

    return {
        "inquiry": inquiry,
        "category": category,
        "category_confidence": conf,
        "sentiment": sentiment,
        "sentiment_confidence": s_conf,
        "urgency": urgency,
        "articles": articles,
        "response": response,
        "response_confidence": r_conf,
        "escalation_required": esc,
        "escalation_reason": esc_reason,
        "reference_id": ref_id,
        "triggered_keyword": esc_kw_hit,
        "steps": steps,
        "knowledge_source": "local",
        "memory_saved": False,
        "execution_mode": "deterministic",
        "tools_used": [s["agent"] for s in steps],
    }


def analyze(inquiry: str) -> dict[str, Any]:
    if st.session_state.use_backend:
        try:
            return call_backend(inquiry, st.session_state.backend_url)
        except Exception:
            return local_analyze(inquiry)
    return local_analyze(inquiry)


# ─────────────────────────────────────────────
# HELPERS / COMPONENTS
# ─────────────────────────────────────────────

def pill_html(label: str, kind: str = "blue", prefix: str = "") -> str:
    css = f"pill pill-{kind}"
    p = f"● {prefix}" if prefix else "●"
    return f'<span class="{css}">{p} {label}</span>'


def confidence_bar(pct: int, label: str = "Confidence") -> str:
    color = "#6EE7B7" if pct >= 75 else ("#FCD34D" if pct >= 55 else "#FCA5A5")
    return f"""
    <div style="margin-bottom:12px">
      <div style="display:flex;justify-content:space-between;margin-bottom:4px">
        <span style="font-size:11px;color:var(--text-muted);font-weight:600;text-transform:uppercase;letter-spacing:.5px">{label}</span>
        <span style="font-size:12px;font-family:var(--mono);color:{color};font-weight:600">{pct}%</span>
      </div>
      <div class="conf-bar-wrap">
        <div class="conf-bar" style="width:{pct}%;background:linear-gradient(90deg,{color},{color}aa)"></div>
      </div>
    </div>"""


def format_timestamp(ts: str | None) -> str:
    if not ts:
        return "—"
    try:
        dt = datetime.fromisoformat(ts)
        return dt.strftime("%H:%M:%S")
    except Exception:
        return ts


def render_agent_timeline(steps: list[dict]) -> None:
    if not steps:
        st.markdown('<div class="empty-state"><div class="empty-state-icon">⬡</div><div class="empty-state-sub">No execution steps recorded</div></div>', unsafe_allow_html=True)
        return

    seen_agents: set[str] = set()
    for step in steps:
        agent_raw = step.get("agent", "Unknown Agent")
        # Deduplicate collaboration echoes — show each agent once
        agent_key = agent_raw.split("_")[0]
        meta = AGENT_META.get(agent_raw, {"icon": "◈", "label": agent_raw, "color": "#94A3B8"})
        details = step.get("details", {})
        is_collab = "collaboration" in details

        collab_class = "collab" if is_collab else ""
        done_class = "done"

        color = meta["color"]
        icon  = meta["icon"]

        # Build detail text
        detail_lines = []
        for k, v in details.items():
            if isinstance(v, list):
                v = ", ".join(str(x) for x in v[:3]) + ("…" if len(v) > 3 else "")
            elif isinstance(v, dict):
                v = json.dumps(v, ensure_ascii=False)[:60] + "…"
            detail_lines.append(f"{k}: {v}")
        detail_text = " · ".join(detail_lines[:4])

        st.markdown(f"""
        <div class="tl-step {done_class}">
          <div class="tl-label" style="color:{color}">
            <span style="margin-right:6px">{icon}</span>{meta['label']}
            {'<span class="badge" style="margin-left:8px;font-size:10px">collab</span>' if is_collab else ''}
          </div>
          <div class="tl-sub">{detail_text[:120]}</div>
        </div>
        """, unsafe_allow_html=True)


def render_articles(articles: list[str]) -> None:
    st.markdown('<div class="section-heading">Knowledge Articles Used</div>', unsafe_allow_html=True)
    for art in articles:
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:8px;padding:8px 12px;background:var(--surface2);border:1px solid var(--border);border-radius:6px;margin-bottom:6px">
          <span style="color:var(--accent);font-size:14px">⬡</span>
          <span style="font-size:13px">{art}</span>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# SIDEBAR
# ─────────────────────────────────────────────

def render_sidebar() -> None:
    with st.sidebar:
        # Logo
        st.markdown("""
        <div class="sidebar-logo">
          <div class="sidebar-logo-icon">⬡</div>
          <div>
            <div class="sidebar-logo-text">SupportAI</div>
            <div class="sidebar-logo-sub">Multi-Agent Platform</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Navigation
        st.markdown('<div class="sidebar-section-label">Navigation</div>', unsafe_allow_html=True)
        view = st.radio(
            "view_radio",
            ["🧑‍💻  Customer Portal", "🛠  Operator Dashboard"],
            label_visibility="collapsed",
        )
        st.session_state.view = "Customer" if "Customer" in view else "Operator"

        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

        # Config
        st.markdown('<div class="sidebar-section-label">Configuration</div>', unsafe_allow_html=True)
        st.session_state.use_backend = st.toggle("Use FastAPI Backend", value=st.session_state.use_backend)
        if st.session_state.use_backend:
            st.session_state.backend_url = st.text_input(
                "Backend URL",
                value=st.session_state.backend_url,
                placeholder="http://127.0.0.1:8000/api/support",
            )

        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

        # Stats summary in sidebar
        tickets = st.session_state.tickets
        total    = len(tickets)
        escalated = sum(1 for t in tickets if t.get("escalation_required"))
        resolved  = total - escalated

        st.markdown('<div class="sidebar-section-label">Session Stats</div>', unsafe_allow_html=True)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown(f"""
            <div style="background:var(--surface2);border:1px solid var(--border);border-radius:8px;padding:12px;text-align:center">
              <div style="font-size:22px;font-weight:700;font-family:var(--mono)">{total}</div>
              <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px">Tickets</div>
            </div>
            """, unsafe_allow_html=True)
        with c2:
            st.markdown(f"""
            <div style="background:rgba(252,165,165,0.08);border:1px solid rgba(252,165,165,0.2);border-radius:8px;padding:12px;text-align:center">
              <div style="font-size:22px;font-weight:700;font-family:var(--mono);color:#FCA5A5">{escalated}</div>
              <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:2px">Escalated</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown('<hr class="divider"/>', unsafe_allow_html=True)
        st.markdown("""
        <div style="font-size:11px;color:var(--text-muted);text-align:center;padding:4px">
          Multi-Agent Customer Support Crew<br>
          <span style="opacity:.5">v2.0 · CrewAI + FastAPI</span>
        </div>
        """, unsafe_allow_html=True)


# ─────────────────────────────────────────────
# CUSTOMER VIEW
# ─────────────────────────────────────────────

def render_customer_view() -> None:
    # Hero header
    st.markdown("""
    <div class="customer-hero">
      <div class="customer-hero-badge">⬡ AI-Powered Support · Multi-Agent</div>
      <div class="customer-hero-title">How can we help you?</div>
      <div class="customer-hero-sub">Our AI agents analyze your request and route it to the right solution instantly.</div>
    </div>
    """, unsafe_allow_html=True)

    # Inquiry form card
    st.markdown('<div class="card-accent">', unsafe_allow_html=True)

    inquiry = st.text_area(
        "Describe your issue",
        placeholder="e.g. My order hasn't arrived and it's been 7 days. I'm really frustrated and need help urgently.",
        height=120,
        key="customer_inquiry",
        label_visibility="collapsed",
    )

    col_btn, col_hint = st.columns([1, 3])
    with col_btn:
        submit = st.button("⬡  Analyze Request", type="primary", use_container_width=True)
    with col_hint:
        st.markdown('<div style="font-size:12px;color:var(--text-muted);padding-top:10px">Processed by 5 specialized AI agents · Typically under 3 seconds</div>', unsafe_allow_html=True)

    st.markdown('</div>', unsafe_allow_html=True)

    if submit:
        if not inquiry.strip():
            st.error("Please describe your issue before submitting.")
            return
        _run_analysis_customer(inquiry.strip())

    # Show result
    result = st.session_state.customer_result
    if result:
        _render_customer_result(result)


def _run_analysis_customer(inquiry: str) -> None:
    agents = [
        ("⬡", "Classifier Agent",         "Analyzing request category…"),
        ("◈", "Sentiment Agent",           "Evaluating emotional tone…"),
        ("⬡", "Knowledge Agent",           "Searching knowledge base…"),
        ("◈", "Response Generation Agent", "Crafting personalized response…"),
        ("⬡", "Escalation Agent",          "Evaluating escalation needs…"),
    ]

    st.markdown('<div class="card" style="margin-top:20px">', unsafe_allow_html=True)
    st.markdown('<div style="font-size:13px;font-weight:600;margin-bottom:14px;color:var(--text-muted)">⬡ Processing your request…</div>', unsafe_allow_html=True)

    placeholders = []
    for icon, name, task in agents:
        ph = st.empty()
        ph.markdown(f"""
        <div class="agent-loading-step">
          <div class="agent-dot-wait"></div>
          <span style="color:var(--text-muted)">{icon} {name}</span>
          <span style="color:var(--text-muted);font-size:11px;margin-left:auto;font-family:var(--mono)">waiting</span>
        </div>
        """, unsafe_allow_html=True)
        placeholders.append((ph, icon, name, task))

    start = time.time()
    # Animate steps
    for i, (ph, icon, name, task) in enumerate(placeholders):
        ph.markdown(f"""
        <div class="agent-loading-step" style="border-color:rgba(56,189,248,0.2);background:rgba(56,189,248,0.04)">
          <div class="agent-dot-active"></div>
          <span>{icon} {name}</span>
          <span style="color:var(--text-muted);font-size:11px;margin-left:auto;font-family:var(--mono)">{task}</span>
        </div>
        """, unsafe_allow_html=True)
        time.sleep(0.35)
        ph.markdown(f"""
        <div class="agent-loading-step" style="border-color:rgba(110,231,183,0.15)">
          <div class="agent-dot-done"></div>
          <span style="color:#6EE7B7">{icon} {name}</span>
          <span style="color:#6EE7B7;font-size:11px;margin-left:auto;font-family:var(--mono)">✓ done</span>
        </div>
        """, unsafe_allow_html=True)

    result = analyze(inquiry)
    elapsed = round(time.time() - start, 2)
    result["_elapsed"] = elapsed
    result["_timestamp"] = datetime.now().isoformat()

    st.markdown('</div>', unsafe_allow_html=True)

    # Store
    st.session_state.customer_result = result
    ticket_record = dict(result)
    ticket_record["_id"] = len(st.session_state.tickets) + 1
    st.session_state.tickets.append(ticket_record)
    st.rerun()


def _render_customer_result(result: dict) -> None:
    esc  = result.get("escalation_required", False)
    sent = result.get("sentiment", "Neutral")
    urg  = result.get("urgency", "Low")
    cat  = result.get("category", "General Support")
    conf = result.get("response_confidence", 0)
    ref  = result.get("reference_id", "—")
    ts   = result.get("_timestamp")
    elapsed = result.get("_elapsed", "—")

    # Status bar
    sent_cfg = SENTIMENT_CONFIG.get(sent, SENTIMENT_CONFIG["Neutral"])
    urg_cfg  = URGENCY_CONFIG.get(urg, URGENCY_CONFIG["Low"])
    cat_icon = CATEGORY_ICONS.get(cat, "💬")

    st.markdown(f"""
    <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:20px 0 12px">
      {pill_html(cat, "blue")}
      {pill_html(sent, "red" if sent == "Concerned" else ("yellow" if sent == "Urgent" else "green"))}
      {pill_html(f"{urg} Urgency", "red" if urg == "High" else ("yellow" if urg == "Medium" else "green"))}
      <span style="margin-left:auto;font-size:11px;color:var(--text-muted);font-family:var(--mono)">
        ⬡ {elapsed}s · {format_timestamp(ts)}
      </span>
    </div>
    """, unsafe_allow_html=True)

    if esc:
        # Escalation notice
        st.markdown(f"""
        <div class="escalation-bubble">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <span style="font-size:20px">⚠️</span>
            <span style="font-size:16px;font-weight:700;color:#FCA5A5">Your request requires human attention</span>
          </div>
          <p style="font-size:14px;line-height:1.7;color:var(--text);margin:0 0 14px">
            Our AI system has identified this as a complex issue that needs a human specialist.
            A support agent will contact you within <strong>24 hours</strong>.
          </p>
          <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;background:rgba(252,165,165,0.08);border-radius:8px">
            <span style="font-size:12px;color:var(--text-muted)">Reference ID:</span>
            <span style="font-family:var(--mono);font-size:13px;font-weight:600;color:#FCA5A5">{ref}</span>
          </div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Response
        response_text = result.get("response", "")
        st.markdown(f"""
        <div style="margin-bottom:8px;display:flex;align-items:center;gap:8px">
          <span style="font-size:11px;font-weight:700;color:var(--text-muted);text-transform:uppercase;letter-spacing:.8px">AI Response</span>
          {pill_html(f"{conf}% Confidence", "green" if conf >= 75 else "yellow")}
        </div>
        <div class="response-bubble">{response_text}</div>
        """, unsafe_allow_html=True)

    # Articles (collapsed)
    articles = result.get("articles", [])
    if articles:
        with st.expander(f"📚 {len(articles)} Knowledge Articles Referenced", expanded=False):
            render_articles(articles)

    # Action buttons
    st.markdown('<div style="margin-top:16px;display:flex;gap:8px;flex-wrap:wrap">', unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        if st.button("👍  Helpful", key="fb_good", use_container_width=True):
            st.success("Thank you for your feedback!")
    with c2:
        if st.button("👎  Not Helpful", key="fb_bad", use_container_width=True):
            st.info("We'll improve. Consider adding more detail.")
    with c3:
        if st.button("🔄  New Inquiry", key="new_inq", use_container_width=True):
            st.session_state.customer_result = None
            st.rerun()
    st.markdown('</div>', unsafe_allow_html=True)


# ─────────────────────────────────────────────
# OPERATOR VIEW
# ─────────────────────────────────────────────

def render_operator_view() -> None:
    # Top navbar
    st.markdown("""
    <div class="top-nav">
      <div>
        <div class="top-nav-title">Operator Dashboard</div>
        <div class="top-nav-sub">Real-time agent monitoring · HITL escalation · Observability</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    tickets = st.session_state.tickets

    # ── METRICS ROW ──
    total     = len(tickets)
    escalated = sum(1 for t in tickets if t.get("escalation_required"))
    resolved  = total - escalated
    avg_conf  = int(sum(t.get("response_confidence", 0) for t in tickets) / total) if total else 0
    high_urg  = sum(1 for t in tickets if t.get("urgency") == "High")

    m1, m2, m3, m4, m5 = st.columns(5)
    with m1:
        st.metric("Total Tickets",    total)
    with m2:
        st.metric("Escalated",        escalated, delta=f"-{resolved} resolved" if resolved else None, delta_color="inverse")
    with m3:
        st.metric("Resolved",         resolved)
    with m4:
        st.metric("Avg Confidence",   f"{avg_conf}%")
    with m5:
        st.metric("High Urgency",     high_urg)

    st.markdown('<hr class="divider"/>', unsafe_allow_html=True)

    # ── MAIN CONTENT ──
    left, right = st.columns([2, 3], gap="large")

    with left:
        _render_ticket_list(tickets)

    with right:
        active = st.session_state.active_ticket
        if active is not None and active < len(tickets):
            _render_ticket_detail(tickets[active])
        else:
            _render_empty_detail()


def _render_ticket_list(tickets: list[dict]) -> None:
    st.markdown('<div class="section-heading">Ticket Queue</div>', unsafe_allow_html=True)

    if not tickets:
        st.markdown("""
        <div class="empty-state" style="padding:32px 16px">
          <div class="empty-state-icon">⬡</div>
          <div class="empty-state-title">No tickets yet</div>
          <div class="empty-state-sub">Submit an inquiry from the Customer Portal to see it here.</div>
        </div>
        """, unsafe_allow_html=True)
        return

    # Filter
    filter_col1, filter_col2 = st.columns(2)
    with filter_col1:
        filter_status = st.selectbox("Filter", ["All", "Escalated", "Resolved"], label_visibility="collapsed")
    with filter_col2:
        filter_cat = st.selectbox("Category", ["All"] + list(CATEGORY_ICONS.keys()), label_visibility="collapsed")

    filtered = tickets
    if filter_status == "Escalated":
        filtered = [t for t in filtered if t.get("escalation_required")]
    elif filter_status == "Resolved":
        filtered = [t for t in filtered if not t.get("escalation_required")]
    if filter_cat != "All":
        filtered = [t for t in filtered if t.get("category") == filter_cat]

    st.markdown(f'<div style="font-size:11px;color:var(--text-muted);margin:6px 0 10px;font-family:var(--mono)">{len(filtered)} ticket{"s" if len(filtered) != 1 else ""}</div>', unsafe_allow_html=True)

    for i, ticket in enumerate(reversed(filtered)):
        idx = len(tickets) - 1 - i  # reverse index
        esc = ticket.get("escalation_required", False)
        cat = ticket.get("category", "General Support")
        urg = ticket.get("urgency", "Low")
        ref = ticket.get("reference_id", f"#{idx+1}")
        inq = ticket.get("inquiry", "")[:55] + ("…" if len(ticket.get("inquiry","")) > 55 else "")
        ts  = format_timestamp(ticket.get("_timestamp"))

        esc_pill = pill_html("ESC", "red") if esc else pill_html("OK", "green")
        urg_dot  = URGENCY_CONFIG.get(urg, URGENCY_CONFIG["Low"])["dot"]
        cat_icon = CATEGORY_ICONS.get(cat, "💬")

        col_info, col_btn = st.columns([5, 1])
        with col_info:
            st.markdown(f"""
            <div class="ticket-row" style="{'border-color:rgba(252,165,165,0.2)' if esc else ''}">
              <span class="ticket-id">{ref[-12:]}</span>
              <span class="ticket-inquiry">{cat_icon} {inq}</span>
              <span style="margin-left:auto;display:flex;align-items:center;gap:8px">
                {esc_pill}
                <span style="font-size:11px;color:var(--text-muted);font-family:var(--mono)">{ts}</span>
              </span>
            </div>
            """, unsafe_allow_html=True)
        with col_btn:
            if st.button("View", key=f"view_ticket_{idx}", use_container_width=True):
                st.session_state.active_ticket = idx
                st.rerun()


def _render_empty_detail() -> None:
    st.markdown("""
    <div class="card" style="height:100%;min-height:300px">
      <div class="empty-state">
        <div class="empty-state-icon">⬡</div>
        <div class="empty-state-title">Select a ticket</div>
        <div class="empty-state-sub">Click <strong>View</strong> on any ticket to see full analysis, agent timeline, and observability data.</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


def _render_ticket_detail(ticket: dict) -> None:
    esc  = ticket.get("escalation_required", False)
    cat  = ticket.get("category", "—")
    sent = ticket.get("sentiment", "Neutral")
    urg  = ticket.get("urgency", "Low")
    ref  = ticket.get("reference_id", "—")
    inq  = ticket.get("inquiry", "")
    resp = ticket.get("response", "")
    esc_reason = ticket.get("escalation_reason", "—")
    triggered  = ticket.get("triggered_keyword")
    elapsed    = ticket.get("_elapsed", "—")
    ts         = ticket.get("_timestamp")
    mode       = ticket.get("execution_mode", "deterministic")
    steps      = ticket.get("steps", [])
    articles   = ticket.get("articles", [])
    r_conf     = ticket.get("response_confidence", 0)
    c_conf     = ticket.get("category_confidence", 0)
    s_conf     = ticket.get("sentiment_confidence", 0)
    tools_used = ticket.get("tools_used", [])
    cat_icon   = CATEGORY_ICONS.get(cat, "💬")
    sent_cfg   = SENTIMENT_CONFIG.get(sent, SENTIMENT_CONFIG["Neutral"])

    # Header
    border_style = "border-color:rgba(252,165,165,0.25)" if esc else ""
    bg_style     = "background:rgba(252,165,165,0.03)" if esc else ""

    st.markdown(f"""
    <div class="card" style="{border_style};{bg_style}">
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:16px">
        <div>
          <div style="font-size:11px;color:var(--text-muted);font-family:var(--mono);margin-bottom:6px">{ref}</div>
          <div style="font-size:15px;font-weight:600;line-height:1.5">{cat_icon} {inq[:80]}{"…" if len(inq) > 80 else ""}</div>
        </div>
        <div style="flex-shrink:0">
          {'<span class="pill pill-red">● ESC</span>' if esc else '<span class="pill pill-green">● Resolved</span>'}
        </div>
      </div>
      <div style="display:flex;gap:8px;flex-wrap:wrap">
        {pill_html(cat, "blue")}
        {pill_html(sent, "red" if sent == "Concerned" else ("yellow" if sent == "Urgent" else "green"))}
        {pill_html(f"{urg} Urgency", "red" if urg == "High" else ("yellow" if urg == "Medium" else "green"))}
        {pill_html(mode, "gray")}
        <span style="margin-left:auto;font-size:11px;color:var(--text-muted);font-family:var(--mono)">{elapsed}s · {format_timestamp(ts)}</span>
      </div>
    </div>
    """, unsafe_allow_html=True)

    # Tabs
    tabs = st.tabs(["📋 Response", "⬡ Agent Timeline", "📚 Knowledge", "🔬 Observability"])

    # ── TAB 1: Response ──
    with tabs[0]:
        if esc:
            st.markdown(f"""
            <div class="escalation-bubble" style="margin-bottom:14px">
              <div style="font-size:13px;font-weight:700;color:#FCA5A5;margin-bottom:8px">⚠ Escalation Required</div>
              <div style="font-size:13px;color:var(--text);margin-bottom:10px">{esc_reason}</div>
              {'<div style="font-size:12px;color:var(--text-muted);font-family:var(--mono)">Keyword trigger: <span style="color:#FCA5A5">'+triggered+'</span></div>' if triggered else ''}
            </div>
            """, unsafe_allow_html=True)

            c1, c2 = st.columns(2)
            with c1:
                if st.button("✅ Approve & Resolve", key=f"approve_{ref}", type="primary", use_container_width=True):
                    idx = st.session_state.active_ticket
                    st.session_state.tickets[idx]["escalation_required"] = False
                    st.session_state.tickets[idx]["escalation_reason"] = "Manually resolved by operator"
                    st.success("Ticket resolved.")
                    st.rerun()
            with c2:
                if st.button("❌ Reject & Escalate", key=f"reject_{ref}", use_container_width=True):
                    st.warning("Ticket marked for team escalation.")
        else:
            st.markdown(f"""
            <div class="response-bubble" style="margin-bottom:14px">{resp}</div>
            """, unsafe_allow_html=True)

        # Confidence bars
        st.markdown(confidence_bar(r_conf, "Response Confidence"), unsafe_allow_html=True)
        st.markdown(confidence_bar(c_conf, "Category Confidence"), unsafe_allow_html=True)
        st.markdown(confidence_bar(s_conf, "Sentiment Confidence"), unsafe_allow_html=True)

    # ── TAB 2: Agent Timeline ──
    with tabs[1]:
        st.markdown('<div class="section-heading" style="margin-bottom:18px">Execution Timeline</div>', unsafe_allow_html=True)
        st.markdown('<div class="card-sm timeline">', unsafe_allow_html=True)
        render_agent_timeline(steps)
        st.markdown('</div>', unsafe_allow_html=True)

        # Tools used pills
        if tools_used:
            st.markdown('<div class="section-heading" style="margin-top:16px">Tools Invoked</div>', unsafe_allow_html=True)
            pills_html = " ".join(f'<span class="pill pill-blue" style="margin-bottom:4px">◈ {t}</span>' for t in tools_used[:8])
            st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:6px">{pills_html}</div>', unsafe_allow_html=True)

    # ── TAB 3: Knowledge ──
    with tabs[2]:
        render_articles(articles)
        st.markdown(f"""
        <div style="margin-top:16px;padding:12px 16px;background:var(--surface2);border:1px solid var(--border);border-radius:8px">
          <div style="font-size:11px;color:var(--text-muted);margin-bottom:4px;font-weight:600;text-transform:uppercase;letter-spacing:.5px">Knowledge Source</div>
          <div style="font-size:13px;font-family:var(--mono)">{ticket.get('knowledge_source','local')}</div>
        </div>
        """, unsafe_allow_html=True)

    # ── TAB 4: Observability ──
    with tabs[3]:
        st.markdown('<div class="section-heading">Raw Execution Data</div>', unsafe_allow_html=True)

        # Summary row
        st.markdown(f"""
        <div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:16px">
          <div class="card-sm" style="flex:1;min-width:120px;text-align:center">
            <div style="font-size:20px;font-weight:700;font-family:var(--mono)">{len(steps)}</div>
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:4px">Agent Steps</div>
          </div>
          <div class="card-sm" style="flex:1;min-width:120px;text-align:center">
            <div style="font-size:20px;font-weight:700;font-family:var(--mono)">{elapsed}s</div>
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:4px">Total Time</div>
          </div>
          <div class="card-sm" style="flex:1;min-width:120px;text-align:center">
            <div style="font-size:20px;font-weight:700;font-family:var(--mono)">{len(tools_used)}</div>
            <div style="font-size:10px;color:var(--text-muted);text-transform:uppercase;letter-spacing:.5px;margin-top:4px">Tools Used</div>
          </div>
        </div>
        """, unsafe_allow_html=True)

        # Accordion per step
        for i, step in enumerate(steps):
            agent_name = step.get("agent", "Unknown")
            meta = AGENT_META.get(agent_name, {"icon": "◈", "label": agent_name, "color": "#94A3B8"})
            details = step.get("details", {})
            details_json = json.dumps(details, indent=2, ensure_ascii=False)
            with st.expander(f"{meta['icon']} Step {i+1}: {meta['label']}", expanded=False):
                st.code(details_json, language="json")

        # Full ticket JSON
        with st.expander("📄 Full Ticket Payload", expanded=False):
            safe = {k: v for k, v in ticket.items() if not k.startswith("_")}
            st.code(json.dumps(safe, indent=2, ensure_ascii=False), language="json")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main() -> None:
    init_state()
    inject_css()
    render_sidebar()

    if st.session_state.view == "Customer":
        render_customer_view()
    else:
        render_operator_view()


if __name__ == "__main__":
    main()
