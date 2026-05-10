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


def _call_backend(inquiry: str, backend_url: str) -> dict | None:
    payload = json.dumps({"inquiry": inquiry}).encode("utf-8")
    request = urllib.request.Request(
        backend_url,
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8")
            return json.loads(payload)
    except (urllib.error.HTTPError, urllib.error.URLError, ValueError):
        return None


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


def _render_stage(idx: int, result: TicketResult) -> None:
    agent = AGENTS[idx]
    stage_title = f"Agent {idx + 1}/{len(AGENTS)}: {agent['name']} {agent['emoji']}"
    stage_body = agent["task"]

    st.markdown(f"### {stage_title}")
    st.write(stage_body)
    with st.spinner("Processando..."):
        time.sleep(0.5)

    if idx == 0:
        st.success(f"✅ Categoria detectada: \"{result.category}\"")
        st.write(f"Confiança: {result.category_confidence}%")
    elif idx == 1:
        st.success(f"✅ Sentimento: \"{result.sentiment_label}\"")
        st.write(f"Urgência: {result.urgency}")
    elif idx == 2:
        st.success(f"✅ Encontrados {len(result.articles)} artigos relevantes")
        for title in result.articles[:3]:
            st.write(f"- \"{title}\"")
    elif idx == 3:
        st.success("✅ Resposta gerada")
        st.write(f"Confiança: {result.response_confidence}%")
    elif idx == 4:
        if result.escalation_required:
            st.warning("⚠️ ESCALATION TRIGGERED")
            st.write(f"Razão: {result.escalation_reason}")
            if result.triggered_keyword:
                st.write(f"Palavra-chave detectada: **{result.triggered_keyword}**")
        else:
            st.success("✅ Sem escalonamento necessário")
            st.write(f"Razão: {result.escalation_reason}")


def _ensure_history() -> None:
    if "history" not in st.session_state:
        st.session_state.history = []


def _append_history(result: TicketResult) -> None:
    st.session_state.history.insert(0, {
        "inquiry": result.inquiry,
        "category": result.category,
        "sentiment": result.sentiment_label,
        "urgency": result.urgency,
        "response": result.response,
        "confidence": result.response_confidence,
        "escalation": result.escalation_required,
        "reference_id": result.reference_id,
    })


def _render_history() -> None:
    st.sidebar.header("Histórico de solicitações")
    if not st.session_state.history:
        st.sidebar.write("Nenhuma solicitação enviada ainda.")
        return

    for entry in st.session_state.history[:10]:
        status = "⚠️ Escalonado" if entry["escalation"] else "✅ Automático"
        with st.sidebar.expander(f"{entry['inquiry'][:40]}...", expanded=False):
            st.write(f"**Categoria:** {entry['category']}")
            st.write(f"**Sentimento:** {entry['sentiment']}")
            st.write(f"**Urgência:** {entry['urgency']}")
            st.write(f"**Confiança:** {entry['confidence']}%")
            st.write(f"**Status:** {status}")
            if entry["escalation"]:
                st.write(f"**Reference ID:** {entry['reference_id']}")
            st.write("---")


def main(argv: list[str] | None = None) -> int:
    _ensure_history()
    st.set_page_config(
        page_title="Multi-Agent Customer Support Crew",
        page_icon="🤖",
        layout="wide",
    )

    st.title("Multi-Agent Customer Support Crew")
    st.write(
        "Uma interface simples para experimentar o fluxo de atendimento ao cliente com agentes de classificação, sentimento, recuperação de conhecimento e escalonamento."
    )

    _render_history()

    st.sidebar.header("Configuração de integração")
    use_backend = st.sidebar.checkbox("Usar backend FastAPI", value=True)
    backend_url = st.sidebar.text_input("URL do backend", value=BACKEND_API_URL)
    st.sidebar.markdown(
        "Use o backend FastAPI para processar a solicitação. Se o backend não estiver disponível, o app executará localmente."
    )

    with st.form(key="support_form"):
        inquiry = st.text_area(
            "Digite sua dúvida ou problema de suporte:",
            height=150,
            placeholder="Ex: Meu pedido #12345 não chegou.",
        )
        submit = st.form_submit_button("Enviar")

    if submit:
        inquiry_text = inquiry.strip()
        if not inquiry_text:
            st.warning("Por favor, informe um texto para sua solicitação.")
            return 0

        if use_backend:
            backend_data = _call_backend(inquiry_text, backend_url)
            if backend_data is not None:
                st.success(f"Executando no backend: {backend_url}")
                result = _build_ticket_result_from_backend(backend_data)
            else:
                st.error(
                    f"Não foi possível conectar ao backend em {backend_url}."
                )
                result = analyze_ticket(inquiry_text)
                st.warning("Usando execução local temporária.")
        else:
            st.info("Executando localmente no frontend Streamlit.")
            result = analyze_ticket(inquiry_text)

        _append_history(result)

        st.info("Processando sua solicitação...")
        progress = st.progress(0)
        stage_container = st.container()

        for idx in range(len(AGENTS)):
            progress.progress(int((idx + 1) / len(AGENTS) * 100))
            with stage_container:
                _render_stage(idx, result)
            time.sleep(0.2)

        st.markdown("---")
        if result.escalation_required:
            st.error("🚨 HUMAN ESCALATION REQUIRED")
            st.write(
                "Sua solicitação foi sinalizada para revisão humana. Um agente de suporte entrará em contato em até 24 horas."
            )
            st.write(f"**Reference ID:** {result.reference_id}")
            st.write("Para assistência imediata, ligue para 1-800-HELP-NOW.")
        else:
            st.success("📋 FINAL RESPONSE")
            st.write(result.response)
            st.write("---")
            st.write(
                "Se quiser, você pode enviar outra solicitação ou adicionar mais detalhes para melhorar a resposta."
            )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
