from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request

import streamlit as st
from aamad.frontend import AGENTS, TicketResult, analyze_ticket

DEFAULT_BACKEND_API_URL = "http://127.0.0.1:8000/api/support"
BACKEND_API_URL = os.environ.get("AAMAD_BACKEND_URL", DEFAULT_BACKEND_API_URL)


def _set_streamlit_style() -> None:
    st.markdown(
        """
        <style>
        .dashboard-card, .stage-card, .ticket-card, .sidebar-card, .section-card {
            border-radius: 20px;
            background: #ffffff;
            padding: 20px;
            border: 1px solid rgba(15, 23, 42, 0.08);
            box-shadow: 0 18px 45px rgba(15, 23, 42, 0.06);
            margin-bottom: 18px;
        }
        .stage-card-header {
            display: flex;
            align-items: center;
            gap: 14px;
            margin-bottom: 14px;
        }
        .stage-icon {
            font-size: 1.5rem;
        }
        .stage-title {
            font-size: 1.05rem;
            font-weight: 700;
            margin-bottom: 4px;
        }
        .stage-subtitle {
            color: #6b7280;
            font-size: 0.92rem;
            line-height: 1.4;
        }
        .stage-row {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 10px;
            color: #111827;
            font-size: 0.96rem;
        }
        .stage-row strong {
            color: #374151;
        }
        .stage-note {
            background: #f8fafc;
            border-radius: 14px;
            padding: 14px;
            color: #334155;
            font-size: 0.93rem;
            line-height: 1.5;
        }
        .status-badge {
            display: inline-flex;
            align-items: center;
            justify-content: center;
            border-radius: 999px;
            padding: 0.45rem 0.85rem;
            font-size: 0.82rem;
            font-weight: 700;
            color: #fff;
        }
        .badge-success {background: #16a34a;}
        .badge-warning {background: #f59e0b;}
        .badge-danger {background: #dc2626;}
        .badge-info {background: #2563eb;}
        .badge-neutral {background: #6b7280;}
        .summary-value {
            font-size: 1.6rem;
            font-weight: 700;
            margin-bottom: 6px;
            color: #111827;
        }
        .summary-label {
            color: #6b7280;
            font-size: 0.9rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        .response-card {
            border-radius: 22px;
            background: linear-gradient(180deg, #ffffff 0%, #f9fafb 100%);
            border: 1px solid rgba(15, 23, 42, 0.08);
            padding: 24px;
            box-shadow: 0 24px 56px rgba(15, 23, 42, 0.08);
        }
        .sidebar-card h4 {
            margin: 0 0 10px;
        }
        .sidebar-card p {
            margin: 4px 0;
            color: #475569;
        }
        .sidebar-section {
            margin-bottom: 18px;
        }
        .hero-title {
            font-size: 2.4rem;
            font-weight: 800;
            margin-bottom: 0.3rem;
            line-height: 1.05;
        }
        .hero-subtitle {
            color: #475569;
            font-size: 1.05rem;
            margin-bottom: 1.5rem;
            line-height: 1.6;
        }
        .small-muted {
            color: #64748b;
            font-size: 0.95rem;
            margin-top: 8px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _format_summary_card(label: str, value: str, note: str, badge: str = None) -> str:
    badge_html = f"<span class='status-badge badge-info'>{badge}</span>" if badge else ""
    return (
        f"<div class='dashboard-card'>"
        f"<div class='summary-label'>{label}</div>"
        f"<div class='summary-value'>{value}</div>"
        f"<div class='small-muted'>{note}</div>"
        f"{badge_html}</div>"
    )


def _call_backend(inquiry_text: str, backend_url: str) -> dict | None:
    """Call backend API to process support inquiry."""
    try:
        payload = json.dumps({"inquiry": inquiry_text}).encode("utf-8")
        request = urllib.request.Request(
            backend_url,
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            response_data = response.read().decode("utf-8")
            return json.loads(response_data)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError) as e:
        st.error(f"Erro ao chamar backend: {e}")
        return None


def _call_backend_status(reference_id: str, backend_url: str) -> dict | None:
    """Get ticket status from backend."""
    status_url = f"{backend_url.rstrip('/support')}/support/{reference_id}/status"
    try:
        with urllib.request.urlopen(status_url, timeout=5) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None


def _call_backend_steps(reference_id: str, backend_url: str) -> dict | None:
    """Get ticket steps from backend."""
    steps_url = f"{backend_url.rstrip('/support')}/support/{reference_id}/steps"
    try:
        with urllib.request.urlopen(steps_url, timeout=5) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None


def _submit_feedback(reference_id: str, backend_url: str, helpful: bool, comments: str = "") -> bool:
    """Submit feedback for a ticket."""
    feedback_url = f"{backend_url.rstrip('/support')}/support/{reference_id}/feedback"
    payload = json.dumps({
        "helpful": helpful,
        "comments": comments
    }).encode("utf-8")
    request = urllib.request.Request(
        feedback_url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


def _approve_ticket(reference_id: str, backend_url: str) -> bool:
    """Approve a ticket."""
    approve_url = f"{backend_url.rstrip('/support')}/support/{reference_id}/approve"
    request = urllib.request.Request(approve_url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


def _reject_ticket(reference_id: str, backend_url: str) -> bool:
    """Reject a ticket."""
    reject_url = f"{backend_url.rstrip('/support')}/support/{reference_id}/reject"
    request = urllib.request.Request(reject_url, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status == 200
    except (urllib.error.HTTPError, urllib.error.URLError):
        return False


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


def _render_stage(idx: int, result: TicketResult, active: bool = False) -> None:
    agent = AGENTS[idx]
    tool_name = [
        "Classification Tool",
        "Sentiment Analysis Tool",
        "Knowledge Retrieval Tool",
        "Response Generation Tool",
        "Escalation Evaluation Tool",
    ][idx]
    if idx == 0:
        status = f"Categoria: {result.category}"
        confidence = f"{result.category_confidence}%"
        result_summary = f"Classificação com foco em palavras-chave do ticket."
    elif idx == 1:
        status = f"Sentimento: {result.sentiment_label}"
        confidence = f"Urgência: {result.urgency}"
        result_summary = f"Análise de tom emocional para priorização do atendimento."
    elif idx == 2:
        status = f"{len(result.articles)} artigos relevantes"
        confidence = f"Base de conhecimento"
        result_summary = "Busca nos artigos de suporte mais relevantes para o caso."
    elif idx == 3:
        status = "Resposta preparada"
        confidence = f"{result.response_confidence}%"
        result_summary = "Geração de resposta clara e alinhada ao contexto do cliente."
    else:
        status = "Escalonamento requisitado" if result.escalation_required else "Sem escalonamento"
        confidence = result.escalation_reason or "Resultado final"
        if result.escalation_required:
            result_summary = "O caso foi sinalizado para revisão humana com prioridade."
        else:
            result_summary = "A resposta automatizada é suficiente para resolver o problema."

    card_html = f"""
    <div class='stage-card'>
      <div class='stage-card-header'>
        <div class='stage-icon'>{agent['emoji']}</div>
        <div>
          <div class='stage-title'>{agent['name']}</div>
          <div class='stage-subtitle'>{agent['task']}</div>
        </div>
      </div>
      <div class='stage-row'><strong>Status</strong><span>{status}</span></div>
      <div class='stage-row'><strong>Ferramenta</strong><span>{tool_name}</span></div>
      <div class='stage-row'><strong>Resultado</strong><span>{confidence}</span></div>
      <div class='stage-note'>{result_summary}</div>
    </div>
    """
    st.markdown(card_html, unsafe_allow_html=True)


def _ensure_history() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []


def _append_history(result: TicketResult, backend_data: dict | None = None) -> None:
    history_entry = {
        "inquiry": result.inquiry,
        "category": result.category,
        "sentiment": result.sentiment_label,
        "urgency": result.urgency,
        "response": result.response,
        "confidence": result.response_confidence,
        "escalation": result.escalation_required,
        "reference_id": result.reference_id,
        "timestamp": time.time(),
    }

    # Add backend-specific data if available
    if backend_data:
        history_entry.update({
            "tools_used": backend_data.get("tools_used", []),
            "skills_used": backend_data.get("skills_used", []),
            "cache_used": backend_data.get("cache_used", False),
            "execution_mode": backend_data.get("execution_mode", "unknown"),
        })

    st.session_state.history.insert(0, history_entry)


def _render_history() -> None:
    st.sidebar.markdown("<div class='sidebar-card'><h4>Histórico de solicitações</h4></div>", unsafe_allow_html=True)
    if not st.session_state.history:
        st.sidebar.write("Nenhuma solicitação enviada ainda.")
        return

    for entry in st.session_state.history[:10]:
        status = "Escalonado" if entry["escalation"] else "Automático"
        badge_tone = "danger" if entry["escalation"] else "success"
        timestamp = time.strftime("%H:%M:%S", time.localtime(entry.get("timestamp", time.time())))
        tools = entry.get("tools_used", [])
        skills = entry.get("skills_used", [])
        cache_used = "Sim" if entry.get("cache_used", False) else "Não"
        mode = entry.get("execution_mode", "local")

        entry_html = f"""
        <div class='sidebar-card'>
          <div><strong>[{timestamp}] {entry['inquiry'][:40]}...</strong></div>
          <p><strong>Categoria:</strong> {entry['category']}</p>
          <p><strong>Sentimento:</strong> {entry['sentiment']}</p>
          <p><strong>Urgência:</strong> {entry['urgency']}</p>
          <p><strong>Confiança:</strong> {entry['confidence']}%</p>
          <p><strong>Status:</strong> <span class='status-badge badge-{badge_tone}'>{status}</span></p>
        """
        if entry["escalation"]:
            entry_html += f"<p><strong>Reference ID:</strong> {entry['reference_id']}</p>"
        if tools:
            entry_html += f"<p><strong>Tools:</strong> {', '.join(tools)}</p>"
        if skills:
            entry_html += f"<p><strong>Skills:</strong> {', '.join(skills)}</p>"
        entry_html += f"<p><strong>Cache:</strong> {cache_used}</p>"
        entry_html += f"<p><strong>Modo:</strong> {mode}</p>"
        entry_html += "</div>"

        st.sidebar.markdown(entry_html, unsafe_allow_html=True)


def main(argv: list[str] | None = None) -> int:
    _ensure_history()
    st.set_page_config(
        page_title="Multi-Agent Customer Support Crew",
        page_icon="🤖",
        layout="wide",
    )
    _set_streamlit_style()

    view_mode = st.sidebar.radio(
        "Modo de visualização",
        ("Customer View", "Operator / Demo View"),
        index=0,
    )
    operator_view = view_mode == "Operator / Demo View"

    if operator_view:
        st.markdown(
            """
            <div style='display:flex; justify-content:space-between; align-items:flex-start; gap:24px;'>
              <div style='max-width:760px;'>
                <div class='hero-title'>Multi-Agent Customer Support Crew</div>
                <div class='hero-subtitle'>Painel de atendimento ao cliente com fluxo de agentes, respostas automatizadas e escalonamento humano quando necessário.</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div style='display:flex; justify-content:space-between; align-items:flex-start; gap:24px;'>
              <div style='max-width:760px;'>
                <div class='hero-title'>Customer Support</div>
                <div class='hero-subtitle'>How can we help you today?</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    sidebar = st.sidebar
    sidebar.markdown("<div class='sidebar-card'><h4>Configuração</h4></div>", unsafe_allow_html=True)
    backend_url = BACKEND_API_URL
    use_backend = True
    if operator_view:
        use_backend = sidebar.checkbox("Usar backend FastAPI", value=True)
        backend_url = sidebar.text_input("URL do backend", value=BACKEND_API_URL)

    if operator_view:
        backend_status = "Disponível"
        badge_tone = "success"
        if use_backend:
            try:
                health_url = backend_url.replace("/api/support", "/health")
                with urllib.request.urlopen(health_url, timeout=2) as response:
                    if response.status != 200:
                        backend_status = "Erro no backend"
                        badge_tone = "danger"
            except Exception:
                backend_status = "Indisponível"
                badge_tone = "warning"

        sidebar.markdown(
            f"<div class='sidebar-card'><div class='stage-row'><strong>Status:</strong><span class='status-badge badge-{badge_tone}'>{backend_status}</span></div>"
            f"<p><strong>URL:</strong> {backend_url}</p>"
            f"<p><strong>Modo:</strong> {'Backend' if use_backend else 'Local'}</p></div>",
            unsafe_allow_html=True,
        )
        sidebar.markdown("<div class='sidebar-card'><h4>Visão rápida</h4><p>Operador técnico com painel de observabilidade, agentes e histórico de tickets.</p></div>", unsafe_allow_html=True)
    else:
        sidebar.markdown("<div class='sidebar-card'><h4>Atendimento ao cliente</h4><p>Use este portal para enviar sua solicitação e receber uma resposta rápida e clara.</p></div>", unsafe_allow_html=True)

    with st.container():
        main_col, summary_col = st.columns([2, 1], gap='large')

        with main_col:
            st.markdown("<div class='section-card'><h4>Solicitação de suporte</h4><p class='small-muted'>Digite sua dúvida ou problema para que nosso time inteligente possa analisar e responder.</p></div>", unsafe_allow_html=True)
            with st.form(key="support_form"):
                inquiry = st.text_area(
                    "Digite sua dúvida ou problema de suporte:",
                    height=170,
                    placeholder="Ex: Meu pedido #12345 não chegou, e o rastreamento não atualiza.",
                )
                submit = st.form_submit_button("Submit request")

        with summary_col:
            if operator_view:
                st.markdown("<div class='section-card'><h4>Indicadores rápidos</h4><div style='display:grid; grid-template-columns:1fr 1fr; gap:14px; margin-top:14px;'>", unsafe_allow_html=True)
                st.markdown("</div></div>", unsafe_allow_html=True)
            else:
                st.markdown("<div class='section-card'><h4>Status</h4><p class='small-muted'>Acompanhe o tempo de resposta e a linha de atendimento.</p></div>", unsafe_allow_html=True)

    if operator_view:
        _render_history()

    if submit:
        inquiry_text = inquiry.strip()
        if not inquiry_text:
            st.warning("Por favor, informe um texto para sua solicitação.")
            return 0

        if use_backend:
            backend_data = _call_backend(inquiry_text, backend_url)
            if backend_data is not None:
                result = _build_ticket_result_from_backend(backend_data)
                _append_history(result, backend_data)
            else:
                if operator_view:
                    st.error(f"Não foi possível conectar ao backend em {backend_url}.")
                else:
                    st.error("Não foi possível processar sua solicitação no momento. Tente novamente em breve.")
                result = analyze_ticket(inquiry_text)
                st.warning("O app usou execução local temporária.")
                _append_history(result)
        else:
            st.info("Executando localmente no frontend Streamlit.")
            result = analyze_ticket(inquiry_text)
            _append_history(result)

        execution_mode = backend_data.get("execution_mode", "local") if backend_data else "local"
        if operator_view:
            summary_html = (
                "<div class='section-card'><h4>Resumo do ticket</h4>"
                "<div style='display:grid; grid-template-columns:repeat(3, minmax(0, 1fr)); gap:14px; margin-top:16px;'>"
                + _format_summary_card("Categoria", result.category, "Classificação detectada pelo agente.")
                + _format_summary_card("Sentimento", result.sentiment_label, "Tonalidade emocional identificada.")
                + _format_summary_card("Urgência", result.urgency, "Prioridade do atendimento.")
                + _format_summary_card("Confiança", f"{result.response_confidence}%", "Confiança na resposta gerada.")
                + _format_summary_card("Status", "Escalonado" if result.escalation_required else "Automático", "Indicador de fluxo final.")
                + _format_summary_card("Modo", execution_mode, "Fonte de execução do processo.")
                + "</div></div>"
            )
            st.markdown(summary_html, unsafe_allow_html=True)

        status_text = st.empty()
        progress = st.progress(0)
        if operator_view:
            status_text.info("Iniciando o fluxo de agentes...")
            for idx in range(len(AGENTS)):
                progress.progress(int((idx + 1) / len(AGENTS) * 100))
                status_text.info(f"{AGENTS[idx]['emoji']} {AGENTS[idx]['name']} em execução")
                _render_stage(idx, result, active=True)
                time.sleep(0.2)
            progress.progress(100)
            status_text.success("Fluxo concluído com sucesso.")
        else:
            status_text.info("Seu pedido está sendo processado. Isso pode levar alguns segundos.")
            for step in range(len(AGENTS)):
                progress.progress(int((step + 1) / len(AGENTS) * 100))
                time.sleep(0.1)
            status_text.success("Processamento concluído.")

        st.markdown("<div class='response-card'>", unsafe_allow_html=True)
        if result.escalation_required:
            st.markdown("<div class='status-badge badge-danger' style='margin-bottom:12px;'>Escalonamento necessário</div>", unsafe_allow_html=True)
            st.markdown("<h3>⚠️ Caso encaminhado para revisão humana</h3>", unsafe_allow_html=True)
            st.markdown(f"<p>{result.escalation_reason}</p>", unsafe_allow_html=True)
            st.markdown(f"<p><strong>Reference ID:</strong> {result.reference_id}</p>", unsafe_allow_html=True)
            st.markdown("<p>Próximo passo: um agente de suporte humano entrará em contato em até 24 horas.</p>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='status-badge badge-success' style='margin-bottom:12px;'>Resposta automatizada</div>", unsafe_allow_html=True)
            st.markdown("<h3>✅ Resposta preparada</h3>", unsafe_allow_html=True)
            st.markdown("<p>Este ticket pode ser resolvido automaticamente sem escalonamento.</p>", unsafe_allow_html=True)
        st.markdown("<hr style='margin:20px 0; border-color: rgba(15,23,42,0.14);'>", unsafe_allow_html=True)
        st.markdown(f"<div style='font-size:1rem; line-height:1.8; color:#111827;'>{result.response}</div>", unsafe_allow_html=True)
        st.markdown(f"<p style='margin-top:18px; font-weight:700;'>Reference ID: {result.reference_id}</p>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        if operator_view and use_backend and backend_data:
            with st.expander("Observabilidade e dados do processamento", expanded=True):
                tools_used = backend_data.get("tools_used", [])
                skills_used = backend_data.get("skills_used", [])
                st.write(f"**Tools used:** {', '.join(tools_used) if tools_used else 'Nenhuma registrada'}")
                st.write(f"**Skills used:** {', '.join(skills_used) if skills_used else 'Nenhuma registrada'}")
                st.write(f"**Cache usado:** {'Sim' if backend_data.get('cache_used', False) else 'Não'}")
                st.write(f"**Modo de execução:** {backend_data.get('execution_mode', 'deterministic')}")
                st.write(f"**Knowledge source:** {backend_data.get('knowledge_source', 'local_files')}")
                st.write(f"**Memory saved:** {'Sim' if backend_data.get('memory_saved', False) else 'Não'}")
                if st.button("Ver passos / logs", key="view_steps"):
                    steps_data = _call_backend_steps(result.reference_id, backend_url)
                    if steps_data:
                        for step in steps_data.get("steps", []):
                            st.write(f"- **{step.get('agent', 'Unknown')}**: {step.get('details', {}).get('tool_used', 'N/A')}")
                    else:
                        st.error("Não foi possível carregar os passos.")

        if operator_view:
            st.markdown("<div class='section-card'><h4>Próxima etapa</h4><p>Você pode enviar outra solicitação ou ajustar seu pedido para refinar o atendimento. Use o histórico lateral para revisar atendimentos anteriores.</p></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div class='section-card'><h4>Obrigado!</h4><p>Sua solicitação foi recebida e estamos trabalhando para oferecer a melhor solução.</p></div>", unsafe_allow_html=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
