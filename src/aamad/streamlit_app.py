from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any

import streamlit as st
from aamad.frontend import TicketResult, analyze_ticket

DEFAULT_BACKEND_API_URL = "http://127.0.0.1:9000/api/support"
BACKEND_API_URL = os.environ.get("AAMAD_BACKEND_URL", DEFAULT_BACKEND_API_URL)


def _init_session_state() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []
    if "selected_ticket_id" not in st.session_state:
        st.session_state.selected_ticket_id = None
    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "Customer View"


def _set_page_style(operator_view: bool) -> None:
    if operator_view:
        background = "#070B16"
        surface = "#111827"
        surface2 = "#161E33"
        text = "#E5E7EB"
        muted = "#94A3B8"
    else:
        background = "#F8FAFC"
        surface = "#FFFFFF"
        surface2 = "#F1F5F9"
        text = "#111827"
        muted = "#475569"

    st.markdown(
        f"""
        <style>
        :root {{
            --bg: {background};
            --surface: {surface};
            --surface2: {surface2};
            --text: {text};
            --text-muted: {muted};
            --accent: #38BDF8;
            --accent2: #6EE7B7;
            --danger: #F87171;
            --warn: #FBBF24;
            --radius: 18px;
            --radius-sm: 12px;
            --shadow: 0 20px 50px rgba(15, 23, 42, 0.18);
        }}

        html, body, [class*="css"] {{
            background: var(--bg) !important;
            color: var(--text) !important;
            font-family: Inter, sans-serif !important;
        }}

        #MainMenu, footer, header {{ visibility: hidden; }}
        .block-container {{ padding: 1.4rem 1.4rem 2rem 1.4rem !important; max-width: 1400px; }}

        .card, .card-sm, .card-ghost {{ background: var(--surface) !important; border: 1px solid rgba(255,255,255,0.08); border-radius: var(--radius); box-shadow: var(--shadow); }}
        .card-sm {{ padding: 18px !important; }}

        .title-large {{ font-size: 2.6rem; font-weight: 800; margin-bottom: 0.2rem; line-height: 1.05; }}
        .subtitle-small {{ font-size: 1rem; color: var(--text-muted); margin-bottom: 24px; }}

        .metric-card {{ padding: 18px 20px; border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.08); background: var(--surface2); }}
        .metric-label {{ text-transform: uppercase; letter-spacing: 0.14em; font-size: 11px; color: var(--text-muted); margin-bottom: 10px; }}
        .metric-value {{ font-size: 2rem; font-weight: 800; line-height: 1; }}
        .metric-note {{ margin-top: 6px; color: var(--text-muted); font-size: 0.92rem; }}

        .pill {{ display: inline-flex; align-items: center; justify-content: center; padding: 6px 12px; border-radius: 999px; font-size: 11px; font-weight: 700; letter-spacing: 0.06em; text-transform: uppercase; }}
        .pill-success {{ color: #10B981; background: rgba(16,185,129,0.12); }}
        .pill-warning {{ color: #FBBF24; background: rgba(251,191,36,0.14); }}
        .pill-danger {{ color: #F87171; background: rgba(248,113,113,0.18); }}
        .pill-neutral {{ color: #94A3B8; background: rgba(148,179,184,0.16); }}
        .pill-primary {{ color: #38BDF8; background: rgba(56,189,248,0.18); }}

        .timeline {{ position: relative; padding-left: 20px; margin-top: 18px; }}
        .timeline::before {{ content: ''; position: absolute; left: 10px; top: 0; bottom: 0; width: 2px; background: rgba(255,255,255,0.08); }}
        .timeline-step {{ position: relative; margin-bottom: 24px; padding-left: 28px; }}
        .timeline-step::before {{ content: ''; position: absolute; left: 0; top: 5px; width: 14px; height: 14px; border-radius: 50%; background: var(--accent); border: 2px solid var(--surface); }}
        .timeline-step.done::before {{ background: #6EE7B7; }}
        .timeline-step.error::before {{ background: #F87171; }}

        .bar-track {{ display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }}
        .bar-label {{ width: 96px; color: var(--text-muted); font-size: 0.9rem; }}
        .bar-container {{ flex: 1; height: 12px; background: rgba(255,255,255,0.08); border-radius: 999px; overflow: hidden; }}
        .bar-fill {{ height: 100%; border-radius: 999px; }}

        .sidebar-section {{ padding: 18px; margin-bottom: 18px; border-radius: var(--radius); border: 1px solid rgba(255,255,255,0.08); background: var(--surface2); }}
        .sidebar-section h4 {{ margin: 0 0 10px; font-size: 14px; color: var(--text); }}
        .sidebar-section p, .sidebar-section span {{ color: var(--text-muted); font-size: 13px; margin: 4px 0; }}

        .support-hero {{ padding: 28px; border-radius: var(--radius); background: var(--surface); border: 1px solid rgba(15,23,42,0.08); box-shadow: var(--shadow); margin-bottom: 24px; }}
        .support-hero h1 {{ margin: 0; font-size: 2.4rem; }}
        .support-hero p {{ margin: 12px 0 0; color: var(--text-muted); font-size: 1rem; }}

        .support-card {{ padding: 24px; border-radius: var(--radius); background: var(--surface); border: 1px solid rgba(15,23,42,0.08); box-shadow: var(--shadow); margin-bottom: 22px; }}
        .support-label {{ margin-bottom: 12px; font-size: 0.92rem; font-weight: 600; color: var(--text-muted); }}
        .support-answer {{ padding: 20px; border-radius: 16px; background: rgba(56,189,248,0.08); border: 1px solid rgba(56,189,248,0.18); }}
        .support-answer h3 {{ margin: 0 0 10px; }}
        .support-answer p {{ margin: 0; line-height: 1.7; }}

        textarea, input, select {{ background: var(--surface2) !important; color: var(--text) !important; border: 1px solid rgba(255,255,255,0.08) !important; }}
        textarea:focus, input:focus {{ border-color: rgba(56,189,248,0.4) !important; box-shadow: 0 0 0 3px rgba(56,189,248,0.1) !important; }}
        .stButton > button {{ border-radius: var(--radius-sm) !important; }}
        .stButton > button[kind="primary"] {{ background: linear-gradient(135deg, #38BDF8, #0EA5E9) !important; color: #0B0F1A !important; }}
        .stButton > button[kind="secondary"] {{ background: rgba(255,255,255,0.04) !important; color: var(--text) !important; border: 1px solid rgba(255,255,255,0.08) !important; }}
        .stTextArea textarea {{ min-height: 150px !important; }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _build_ticket_result_from_backend(data: dict) -> TicketResult:
    return TicketResult(
        inquiry=data.get("inquiry", ""),
        category=data.get("category", "General Support"),
        category_confidence=data.get("category_confidence", 0),
        sentiment_label=data.get("sentiment", "Neutral"),
        sentiment_confidence=data.get("sentiment_confidence", 0),
        urgency=data.get("urgency", "Low"),
        articles=data.get("articles", []),
        response=data.get("response", ""),
        response_confidence=data.get("response_confidence", 0),
        escalation_required=data.get("escalation_required", False),
        escalation_reason=data.get("escalation_reason", ""),
        reference_id=data.get("reference_id", ""),
        triggered_keyword=data.get("triggered_keyword"),
    )


def _call_backend(inquiry_text: str, backend_url: str) -> dict | None:
    try:
        payload = json.dumps({"inquiry": inquiry_text}).encode("utf-8")
        request = urllib.request.Request(
            backend_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        st.error(f"Erro ao chamar backend: {e}")
        return None


def _call_backend_status(backend_url: str) -> tuple[str, str]:
    health_url = backend_url.rstrip("/").replace("/api/support", "/health")
    try:
        with urllib.request.urlopen(health_url, timeout=3) as response:
            if response.status == 200:
                return "Online", "success"
    except Exception:
        pass
    return "Offline", "danger"


def _call_backend_steps(reference_id: str, backend_url: str) -> dict | None:
    steps_url = backend_url.rstrip("/").replace("/api/support", f"/api/support/{reference_id}/steps")
    try:
        with urllib.request.urlopen(steps_url, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception:
        return None


def _approve_ticket(reference_id: str, backend_url: str) -> bool:
    approve_url = backend_url.rstrip("/").replace("/api/support", f"/api/support/{reference_id}/approve")
    request = urllib.request.Request(approve_url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def _reject_ticket(reference_id: str, backend_url: str) -> bool:
    reject_url = backend_url.rstrip("/").replace("/api/support", f"/api/support/{reference_id}/reject")
    request = urllib.request.Request(reject_url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except Exception:
        return False


def _format_pill(label: str, tone: str) -> str:
    return f"<span class='pill pill-{tone}'>{label}</span>"


def _render_metric_card(label: str, value: str, note: str) -> None:
    st.markdown(
        f"""
        <div class='metric-card'>
          <div class='metric-label'>{label}</div>
          <div class='metric-value'>{value}</div>
          <div class='metric-note'>{note}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_sentiment_bars(sentiment_counts: dict[str, int]) -> None:
    total = sum(sentiment_counts.values()) or 1
    colors = {
        "Positive": "#6EE7B7",
        "Neutral": "#38BDF8",
        "Concerned": "#FBBF24",
        "Urgent": "#F87171",
    }
    for label, count in sentiment_counts.items():
        width = int(count / total * 100)
        color = colors.get(label, "#38BDF8")
        st.markdown(
            f"""
            <div class='bar-track'>
              <div class='bar-label'>{label}</div>
              <div class='bar-container'><div class='bar-fill' style='width:{width}%; background:{color};'></div></div>
              <div style='min-width:32px; color: var(--text);'>{count}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _create_history_entry(result: TicketResult, backend_data: dict | None) -> dict[str, Any]:
    return {
        "inquiry": result.inquiry,
        "category": result.category,
        "sentiment": result.sentiment_label,
        "urgency": result.urgency,
        "response": result.response,
        "confidence": result.response_confidence,
        "escalation": result.escalation_required,
        "reference_id": result.reference_id,
        "timestamp": datetime.now().isoformat(),
        "backend_data": backend_data,
    }


def _build_history_selector() -> None:
    history = st.session_state.history
    if not history:
        st.sidebar.write("Nenhum ticket disponível")
        return

    labels = [f"{entry['reference_id']} — {entry['category']} ({entry['sentiment']})" for entry in history]
    mapping = {label: entry['reference_id'] for label, entry in zip(labels, history)}

    current_label = None
    if st.session_state.selected_ticket_id:
        for label, ref in mapping.items():
            if ref == st.session_state.selected_ticket_id:
                current_label = label
                break

    selected_label = st.sidebar.selectbox("Selecionar ticket", labels, index=labels.index(current_label) if current_label in labels else 0)
    st.session_state.selected_ticket_id = mapping[selected_label]


def _selected_ticket() -> dict | None:
    if not st.session_state.history:
        return None
    selected_id = st.session_state.selected_ticket_id or st.session_state.history[0]["reference_id"]
    for entry in st.session_state.history:
        if entry["reference_id"] == selected_id:
            return entry
    return st.session_state.history[0]


def _render_operator_sidebar(backend_url: str, backend_status: str, backend_tone: str) -> None:
    st.sidebar.markdown(
        "<div class='sidebar-section'><h4>Operator Dashboard</h4><p>AI Operations / Demo View</p></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"<div class='sidebar-section'><h4>Backend</h4><p>{backend_url}</p><p>Status: {_format_pill(backend_status, backend_tone)}</p></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown("<div class='sidebar-section'><h4>Ticket history</h4></div>", unsafe_allow_html=True)
    _build_history_selector()
    ticket = _selected_ticket()
    if ticket:
        st.sidebar.markdown(
            "<div class='sidebar-section'><h4>Selected ticket</h4>"
            f"<p><strong>Ref:</strong> {ticket['reference_id']}</p>"
            f"<p><strong>Category:</strong> {ticket['category']}</p>"
            f"<p><strong>Sentiment:</strong> {ticket['sentiment']}</p>"
            f"<p><strong>Urgency:</strong> {ticket['urgency']}</p>"
            f"<p><strong>Escalated:</strong> {'Yes' if ticket['escalation'] else 'No'}</p>"
            "</div>",
            unsafe_allow_html=True,
        )


def _render_customer_sidebar(backend_url: str) -> None:
    st.sidebar.markdown(
        "<div class='sidebar-section'><h4>Customer Portal</h4><p>Submit your issue clearly and receive a helpful response.</p></div>",
        unsafe_allow_html=True,
    )
    st.sidebar.markdown(
        f"<div class='sidebar-section'><h4>Backend</h4><p>{backend_url}</p></div>",
        unsafe_allow_html=True,
    )


def _render_operator_header() -> None:
    st.markdown(
        "<div class='card'><div class='title-large'>AI Operations Dashboard</div><div class='subtitle-small'>Dark mode enterprise view with KPI, analytics, ticket controls, and observability.</div></div>",
        unsafe_allow_html=True,
    )


def _render_customer_header() -> None:
    st.markdown(
        "<div class='support-hero'><h1>Customer Support Portal</h1><p>Describe your issue and our system will analyze it and return a response.</p></div>",
        unsafe_allow_html=True,
    )


def _render_ticket_summary(ticket: dict[str, Any]) -> None:
    st.markdown(
        "<div class='card'>"
        f"<h4>Ticket details</h4>"
        f"<p><strong>Reference:</strong> {ticket['reference_id']}</p>"
        f"<p><strong>Inquiry:</strong> {ticket['inquiry']}</p>"
        f"<p><strong>Category:</strong> {ticket['category']}</p>"
        f"<p><strong>Sentiment:</strong> {ticket['sentiment']}</p>"
        f"<p><strong>Urgency:</strong> {ticket['urgency']}</p>"
        f"<p><strong>Confidence:</strong> {ticket['confidence']}%</p>"
        f"<p><strong>Status:</strong> {'Escalated' if ticket['escalation'] else 'Automated'}</p>"
        f"<p><strong>Escalation reason:</strong> {ticket['backend_data'].get('escalation_reason', 'N/A') if ticket['backend_data'] else 'N/A'}</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_operator_ticket_banner(ticket: dict[str, Any]) -> None:
    escalation_pill = "pill-danger" if ticket["escalation"] else "pill-success"
    escalation_label = "Yes" if ticket["escalation"] else "No"
    st.markdown(
        "<div class='card'>"
        f"<h4>Selected ticket summary</h4>"
        f"<p><strong>Reference:</strong> {ticket['reference_id']}</p>"
        f"<p><strong>Category:</strong> {ticket['category']} - <span class='pill pill-primary'>{ticket['sentiment']}</span></p>"
        f"<p><strong>Urgency:</strong> <span class='pill pill-warning'>{ticket['urgency']}</span></p>"
        f"<p><strong>Escalated:</strong> <span class='pill {escalation_pill}'>{escalation_label}</span></p>"
        f"<p><strong>Confidence:</strong> {ticket['confidence']}%</p>"
        "</div>",
        unsafe_allow_html=True,
    )


def _render_agent_timeline(result: TicketResult, backend_data: dict | None) -> None:
    if backend_data and backend_data.get("steps"):
        steps = []
        for step in backend_data["steps"]:
            details = step.get("details", {})
            steps.append(
                {
                    "agent": step.get("agent", "Unknown"),
                    "tool": details.get("tool_used", "Unknown"),
                    "summary": str(details.get("output", details)),
                    "confidence": details.get("confidence", "n/a") if isinstance(details, dict) else "n/a",
                    "status": "done",
                }
            )
    else:
        steps = [
            {"agent": "Classifier Agent", "tool": "Classification Tool", "summary": f"Category: {result.category}", "confidence": f"{result.category_confidence}%", "status": "done"},
            {"agent": "Sentiment Agent", "tool": "Sentiment Analysis Tool", "summary": f"Sentiment: {result.sentiment_label}", "confidence": f"{result.sentiment_confidence}%", "status": "done"},
            {"agent": "Knowledge Agent", "tool": "Knowledge Retrieval Tool", "summary": f"Articles: {len(result.articles)}", "confidence": "n/a", "status": "done"},
            {"agent": "Response Generation Agent", "tool": "Response Generation Tool", "summary": f"Response confidence {result.response_confidence}%", "confidence": f"{result.response_confidence}%", "status": "done"},
            {"agent": "Escalation Agent", "tool": "Escalation Evaluation Tool", "summary": "Escalated" if result.escalation_required else "No escalation", "confidence": "n/a", "status": "error" if result.escalation_required else "done"},
        ]

    html = "<div class='timeline'>"
    for step in steps:
        tone = "error" if step["status"] == "error" else "done"
        html += (
            f"<div class='timeline-step {tone}'>"
            f"<strong>{step['agent']}</strong> &middot; <span class='pill pill-primary'>{step['tool']}</span>"
            f"<div class='custom-small'>{step['summary']}</div>"
            f"<div class='custom-small'>Confidence: {step['confidence']}</div>"
            f"</div>"
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _render_observability_tabs(backend_data: dict | None, history_ticket: dict | None) -> None:
    tabs = st.tabs(["Overview", "Sentiment", "Agents", "Tools", "Skills", "Logs", "Integrations", "Memory"])

    with tabs[0]:
        st.markdown("<div class='card'><h4>Overview</h4><p>Quick insight for the selected ticket.</p></div>", unsafe_allow_html=True)
        if backend_data:
            st.write({
                "Execution mode": backend_data.get("execution_mode", "unknown"),
                "Knowledge source": backend_data.get("knowledge_source", "unknown"),
                "Cache used": backend_data.get("cache_used", False),
            })
        else:
            st.write("No backend details available.")

    with tabs[1]:
        st.markdown("<div class='card'><h4>Sentiment</h4></div>", unsafe_allow_html=True)
        if history_ticket:
            st.markdown(f"<p><strong>Current ticket sentiment:</strong> {history_ticket['sentiment']}</p>", unsafe_allow_html=True)
            st.markdown(f"<p><strong>Urgency level:</strong> {history_ticket['urgency']}</p>", unsafe_allow_html=True)
            _render_sentiment_bars({history_ticket['sentiment']: 1, "Neutral": 0})
        else:
            st.write("No ticket selected.")

    with tabs[2]:
        st.markdown("<div class='card'><h4>Agents</h4></div>", unsafe_allow_html=True)
        if backend_data and backend_data.get("steps"):
            for step in backend_data["steps"]:
                st.write(f"**{step.get('agent')}** — {step.get('details', {}).get('tool_used', 'N/A')}")
                st.write(step.get('details', {}).get('output', {}))
        else:
            st.write("No agent details available.")

    with tabs[3]:
        st.markdown("<div class='card'><h4>Tools</h4></div>", unsafe_allow_html=True)
        st.write(backend_data.get("tools_used", [])) if backend_data else st.write("No tool data available.")

    with tabs[4]:
        st.markdown("<div class='card'><h4>Skills</h4></div>", unsafe_allow_html=True)
        st.write(backend_data.get("skills_used", [])) if backend_data else st.write("No skill data available.")

    with tabs[5]:
        st.markdown("<div class='card'><h4>Logs</h4></div>", unsafe_allow_html=True)
        if backend_data and backend_data.get("steps"):
            for step in backend_data["steps"]:
                st.write(step)
        else:
            st.write("No logs available.")

    with tabs[6]:
        st.markdown("<div class='card'><h4>Integrations</h4></div>", unsafe_allow_html=True)
        st.write({
            "REST API tool": "Ready",
            "GraphQL API tool": "Ready",
            "CRM mock": "Ready",
            "Ticketing mock": "Ready",
            "Notification mock": "Ready",
            "PostgreSQL-ready": "Ready",
            "JSON fallback": "Enabled",
            "Redis-ready": "Disabled",
        })

    with tabs[7]:
        st.markdown("<div class='card'><h4>Memory</h4></div>", unsafe_allow_html=True)
        st.write("Memory support is available when enabled in backend configuration.")
        if backend_data:
            st.write(f"Memory saved: {backend_data.get('memory_saved', False)}")


def _render_hitl_controls(ticket: dict[str, Any], backend_url: str) -> None:
    st.markdown("<div class='card'><h4>Human-in-the-loop</h4><p>Approve, reject, request revision or escalate manually.</p>", unsafe_allow_html=True)
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Approve ticket"):
            success = _approve_ticket(ticket['reference_id'], backend_url)
            st.success("Approved." if success else "Falha ao aprovar.")
        if st.button("Reject ticket"):
            success = _reject_ticket(ticket['reference_id'], backend_url)
            st.success("Rejeitado." if success else "Falha ao rejeitar.")
    with col_b:
        if st.button("Request revision"):
            st.info("Solicitação de revisão registrada.")
        if st.button("Escalate manually"):
            st.warning("Escalonamento manual acionado.")
    comments = st.text_area("Feedback comments", height=100)
    if comments:
        st.info("Comentário registrado localmente.")
    st.markdown(
        f"<p><strong>Current approval status:</strong> {ticket['backend_data'].get('escalation_reason', 'N/A') if ticket['backend_data'] else 'N/A'}</p></div>",
        unsafe_allow_html=True,
    )


def main(argv: list[str] | None = None) -> int:
    _init_session_state()
    st.set_page_config(page_title="Multi-Agent Customer Support Crew", page_icon="🤖", layout="wide")

    view_mode = st.sidebar.radio(
        "Modo de visualização",
        ("Customer View", "Operator / Demo View"),
        index=0 if st.session_state.view_mode == "Customer View" else 1,
        key="view_mode",
    )
    operator_view = view_mode == "Operator / Demo View"
    _set_page_style(operator_view)

    backend_url = st.sidebar.text_input("Backend URL", value=BACKEND_API_URL)
    use_backend = st.sidebar.checkbox("Usar backend FastAPI", value=True)
    backend_status, backend_tone = _call_backend_status(backend_url) if operator_view and use_backend else ("Local", "warning")

    if operator_view:
        _render_operator_sidebar(backend_url, backend_status, backend_tone)
        _render_operator_header()
    else:
        _render_customer_sidebar(backend_url)
        _render_customer_header()

    with st.form(key="support_form"):
        if not operator_view:
            st.markdown(
                "<div class='support-card'><div class='support-label'>Submit your request</div><h3>How can we help today?</h3><p>Describe your issue clearly so we can route it correctly.</p></div>",
                unsafe_allow_html=True,
            )
        inquiry = st.text_area("Your support inquiry", height=160, placeholder="Example: My order #12345 hasn't arrived yet.")
        submit = st.form_submit_button("Send request")

    if submit:
        if not inquiry.strip():
            st.warning("Por favor, informe um texto para sua solicitação.")
            return 0

        backend_data = None
        if use_backend:
            backend_data = _call_backend(inquiry.strip(), backend_url)
        if backend_data:
            result = _build_ticket_result_from_backend(backend_data)
        else:
            if use_backend and operator_view:
                st.error("Não foi possível conectar ao backend. Usando fallback local.")
            result = analyze_ticket(inquiry.strip())
            backend_data = None

        history_entry = _create_history_entry(result, backend_data)
        st.session_state.history.insert(0, history_entry)
        st.session_state.selected_ticket_id = history_entry["reference_id"]

        if operator_view:
            total = len(st.session_state.history)
            escalated = sum(1 for item in st.session_state.history if item["escalation"])
            automated = total - escalated
            avg_confidence = round(sum(item["confidence"] for item in st.session_state.history) / total, 1)
            urgency_map = {"Low": 1, "Medium": 2, "High": 3}
            average_urgency = sum(urgency_map.get(item["urgency"], 1) for item in st.session_state.history) / total
            avg_urgency_label = "High" if average_urgency > 2.2 else "Medium" if average_urgency > 1.2 else "Low"
            sentiment_counts = {
                "Positive": sum(1 for item in st.session_state.history if item["sentiment"] == "Neutral"),
                "Neutral": sum(1 for item in st.session_state.history if item["sentiment"] == "Neutral"),
                "Concerned": sum(1 for item in st.session_state.history if item["sentiment"] == "Concerned"),
                "Urgent": sum(1 for item in st.session_state.history if item["sentiment"] == "Urgent"),
            }

            st.markdown("<div class='card'><div style='display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px;'>", unsafe_allow_html=True)
            _render_metric_card("Total tickets", str(total), "Volume total de solicitações.")
            _render_metric_card("Escalated tickets", str(escalated), "Tickets que exigem revisão humana.")
            _render_metric_card("Automated tickets", str(automated), "Tickets resolvidos automaticamente.")
            _render_metric_card("Average confidence", f"{avg_confidence}%", "Confiança média da equipe de agentes.")
            st.markdown("</div></div>", unsafe_allow_html=True)

            st.markdown("<div class='card' style='margin-top:18px;'><div style='display:grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 16px;'>", unsafe_allow_html=True)
            _render_metric_card("Average urgency", avg_urgency_label, "Urgência média calculada.")
            _render_metric_card("Sentiment summary", ", ".join([k for k, v in sentiment_counts.items() if v > 0]) or "None", "Resumo de emoções capturadas.")
            _render_metric_card("Backend status", backend_status, "Status de conexão com a API.")
            _render_metric_card("Execution mode", backend_data.get("execution_mode", "local") if backend_data else "local", "Fonte de processamento.")
            st.markdown("</div></div>", unsafe_allow_html=True)

            selected = _selected_ticket()
            if selected:
                _render_operator_ticket_banner(selected)
            if selected:
                left, right = st.columns([2, 1], gap="large")
                with left:
                    st.markdown("<div class='card'><h4>Sentiment analytics</h4><p>Current ticket sentiment and urgency overview.</p></div>", unsafe_allow_html=True)
                    st.markdown(f"<p><strong>Sentiment:</strong> {selected['sentiment']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p><strong>Urgency:</strong> {selected['urgency']}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p><strong>Trigger keyword:</strong> {selected['backend_data'].get('triggered_keyword', 'None') if selected['backend_data'] else 'None'}</p>", unsafe_allow_html=True)
                    _render_sentiment_bars(sentiment_counts)
                    st.markdown("<div class='card'><h4>Agent execution timeline</h4></div>", unsafe_allow_html=True)
                    _render_agent_timeline(result, backend_data)
                    _render_observability_tabs(backend_data, selected)

                with right:
                    _render_ticket_summary(selected)
                    _render_hitl_controls(selected, backend_url)
                    st.markdown("<div class='card'><h4>Integrations readiness</h4><p>Mock integrations and readiness indicators.</p></div>", unsafe_allow_html=True)
                    st.write({
                        "REST API tool": "Ready",
                        "GraphQL API tool": "Ready",
                        "CRM mock": "Ready",
                        "Ticketing mock": "Ready",
                        "Notification mock": "Ready",
                        "PostgreSQL-ready": "Ready",
                        "JSON fallback": "Enabled",
                        "Redis-ready": "Disabled",
                    })
            else:
                st.info("Selecione um ticket no painel lateral para ver detalhes do fluxo.")

        else:
            st.markdown("<div class='support-card'><div class='support-label'>Response</div><h3>Resposta preparada</h3><p>Seu ticket foi processado com sucesso.</p></div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='card'><h4>Ticket result</h4>"
                f"<p><strong>Category:</strong> {result.category}</p>"
                f"<p><strong>Sentiment:</strong> {result.sentiment_label}</p>"
                f"<p><strong>Urgency:</strong> {result.urgency}</p>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown(f"<div class='support-answer'><p>{result.response}</p></div>", unsafe_allow_html=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
