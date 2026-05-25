from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table,
    TableStyle, PageBreak,
)
from io import BytesIO
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

PURPLE       = colors.HexColor("#7C3AED")
PURPLE_LIGHT = colors.HexColor("#EDE9FE")
GREEN        = colors.HexColor("#059669")
GREEN_LIGHT  = colors.HexColor("#D1FAE5")
RED          = colors.HexColor("#DC2626")
RED_LIGHT    = colors.HexColor("#FEE2E2")
YELLOW       = colors.HexColor("#D97706")
YELLOW_LIGHT = colors.HexColor("#FEF3C7")
GRAY_DARK    = colors.HexColor("#1F2937")
GRAY_MID     = colors.HexColor("#6B7280")
GRAY_LIGHT   = colors.HexColor("#F9FAFB")
WHITE        = colors.white


def _styles():
    return {
        "title": ParagraphStyle(
            "title", fontSize=28, fontName="Helvetica-Bold",
            textColor=WHITE, alignment=TA_CENTER, spaceAfter=4,
        ),
        "subtitle": ParagraphStyle(
            "subtitle", fontSize=12, fontName="Helvetica",
            textColor=PURPLE_LIGHT, alignment=TA_CENTER, spaceAfter=2,
        ),
        "body": ParagraphStyle(
            "body", fontSize=10, fontName="Helvetica",
            textColor=GRAY_DARK, spaceAfter=4,
        ),
    }


def _header_footer(canvas, doc):
    canvas.saveState()
    w, _ = A4

    canvas.setStrokeColor(PURPLE_LIGHT)
    canvas.setLineWidth(0.5)
    canvas.line(2 * cm, 1.5 * cm, w - 2 * cm, 1.5 * cm)

    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GRAY_MID)
    canvas.drawString(2 * cm, 1.1 * cm, "Agentic Support Platform — Confidential Report")
    canvas.drawRightString(
        w - 2 * cm, 1.1 * cm,
        f"Page {doc.page} · {datetime.now().strftime('%d/%m/%Y')}",
    )
    canvas.restoreState()


def _section_header(title: str, width: float):
    data = [[Paragraph(title, ParagraphStyle(
        "sh", fontSize=13, fontName="Helvetica-Bold", textColor=WHITE,
    ))]]
    table = Table(data, colWidths=[width])
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), GRAY_DARK),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LEFTPADDING",   (0, 0), (-1, -1), 12),
    ]))
    return table


def _kpi_table(metrics, width):
    total    = metrics.get("total_runs", 0)
    resolved = metrics.get("resolved", 0)
    escalated = metrics.get("escalated", 0)
    csat     = metrics.get("csat_score", 0) or 0

    res_pct = round(resolved / total * 100) if total else 0
    esc_pct = round(escalated / total * 100) if total else 0

    def _v(text, color):
        return Paragraph(text, ParagraphStyle(
            "v", fontSize=28, fontName="Helvetica-Bold",
            textColor=color, alignment=TA_CENTER,
        ))

    def _l(text):
        return Paragraph(text, ParagraphStyle(
            "l", fontSize=9, fontName="Helvetica",
            textColor=GRAY_MID, alignment=TA_CENTER,
        ))

    data = [
        [
            _v(str(total),         colors.HexColor("#2563EB")),
            _v(str(resolved),      GREEN),
            _v(str(escalated),     RED),
            _v(f"{csat:.0f}%",     PURPLE),
        ],
        [
            _l("Total Tickets"),
            _l(f"Resolved ({res_pct}%)"),
            _l(f"Escalated ({esc_pct}%)"),
            _l("CSAT Score"),
        ],
    ]

    col_width = width / 4
    table = Table(data, colWidths=[col_width] * 4)
    table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (0, 1), colors.HexColor("#DBEAFE")),
        ("BACKGROUND",    (1, 0), (1, 1), GREEN_LIGHT),
        ("BACKGROUND",    (2, 0), (2, 1), RED_LIGHT),
        ("BACKGROUND",    (3, 0), (3, 1), PURPLE_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 12),
        ("LEFTPADDING",   (0, 0), (-1, -1), 8),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, WHITE),
    ]))
    return table


def generate_pdf_report(
    tickets: list,
    metrics: dict,
    agent_metrics: list,
    cost_forecast: dict,
    resolution_time: list,
    period: str = "All time",
) -> BytesIO:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=2 * cm,
        leftMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2.5 * cm,
        title="Agentic Support Platform Report",
        author="Agentic Support Platform",
    )

    styles = _styles()
    story  = []
    w      = A4[0] - 4 * cm

    # ── PAGE 1: COVER + SUMMARY ─────────────────────────────────────
    cover_table = Table([[Paragraph("Agentic Support Platform", styles["title"])]], colWidths=[w])
    cover_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), PURPLE),
        ("TOPPADDING",    (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("LEFTPADDING",   (0, 0), (-1, -1), 16),
        ("RIGHTPADDING",  (0, 0), (-1, -1), 16),
    ]))
    story.append(cover_table)
    story.append(Spacer(1, 0.3 * cm))

    sub_table = Table([[Paragraph(
        f"Analytics Report · {period} · "
        f"Generated {datetime.now().strftime('%d %B %Y')}",
        styles["subtitle"],
    )]], colWidths=[w])
    sub_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, -1), PURPLE_LIGHT),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(sub_table)
    story.append(Spacer(1, 0.8 * cm))

    story.append(_section_header("Executive Summary", w))
    story.append(Spacer(1, 0.3 * cm))
    story.append(_kpi_table(metrics, w))
    story.append(Spacer(1, 0.6 * cm))

    # Category table
    story.append(_section_header("Tickets by Category", w))
    story.append(Spacer(1, 0.3 * cm))

    categories = metrics.get("by_category", [])
    total_runs = metrics.get("total_runs", 1) or 1

    def _p(text, **kw):
        return Paragraph(str(text), ParagraphStyle("_p", fontSize=10, fontName="Helvetica", **kw))

    cat_data = [["Category", "Tickets", "% Total", "Trend"]]
    for cat in categories:
        pct   = round(cat.get("count", 0) / total_runs * 100, 1)
        trend = "High" if pct > 30 else "Low" if pct < 10 else "Mid"
        cat_data.append([
            cat.get("category", ""),
            str(cat.get("count", 0)),
            f"{pct}%",
            trend,
        ])

    cat_table = Table(cat_data, colWidths=[w * 0.45, w * 0.2, w * 0.2, w * 0.15])
    cat_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), GRAY_DARK),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0), (-1, -1), 10),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, GRAY_LIGHT]),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story.append(cat_table)

    story.append(PageBreak())

    # ── PAGE 2: RESOLUTION TIME + AGENTS ────────────────────────────
    story.append(_section_header("Resolution Time by Category", w))
    story.append(Spacer(1, 0.3 * cm))

    rt_data = [["Category", "Avg (s)", "Min (s)", "Max (s)", "Speed"]]
    for rt in (resolution_time or []):
        avg   = rt.get("avg_time_sec", 0)
        speed = "Fast" if avg < 8 else "Medium" if avg < 12 else "Slow"
        rt_data.append([
            rt.get("category", ""),
            f"{rt.get('avg_time_sec', 0):.1f}",
            f"{rt.get('min_time_sec', 0):.1f}",
            f"{rt.get('max_time_sec', 0):.1f}",
            speed,
        ])

    if len(rt_data) > 1:
        rt_table = Table(rt_data, colWidths=[w * 0.35, w * 0.15, w * 0.15, w * 0.15, w * 0.2])
        rt_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), GRAY_DARK),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 10),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, GRAY_LIGHT]),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        story.append(rt_table)

    story.append(Spacer(1, 0.6 * cm))

    story.append(_section_header("Agent Performance", w))
    story.append(Spacer(1, 0.3 * cm))

    agent_data = [["Agent", "Calls", "Avg Latency", "Cost/Call", "Mode"]]
    for agent in (agent_metrics or []):
        mode = agent.get("execution_mode", "llm")
        mode_label = "LLM" if mode == "llm" else "Rules"
        agent_data.append([
            str(agent.get("step_name", agent.get("agent_name", "")))[:30],
            str(agent.get("calls", 0)),
            f"{agent.get('avg_latency_ms', 0):.0f}ms",
            f"${agent.get('avg_cost_usd', 0):.6f}",
            mode_label,
        ])

    if len(agent_data) > 1:
        agent_table = Table(agent_data, colWidths=[w * 0.35, w * 0.1, w * 0.2, w * 0.2, w * 0.15])
        agent_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0), PURPLE),
            ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
            ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE",      (0, 0), (-1, -1), 9),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, PURPLE_LIGHT]),
            ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
            ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING",    (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
        ]))
        story.append(agent_table)

    story.append(PageBreak())

    # ── PAGE 3: COST ANALYSIS ───────────────────────────────────────
    story.append(_section_header("Cost Analysis & Forecasting", w))
    story.append(Spacer(1, 0.3 * cm))

    projections = cost_forecast.get("projections", {})
    avg_daily   = cost_forecast.get("avg_daily_tickets", 0)

    proj_data = [
        ["Period", "Projected Cost", "Est. Tickets"],
        ["Daily",   f"${projections.get('daily_usd', 0):.4f}",   f"~{avg_daily:.0f}"],
        ["Weekly",  f"${projections.get('weekly_usd', 0):.4f}",  f"~{avg_daily * 7:.0f}"],
        ["Monthly", f"${projections.get('monthly_usd', 0):.4f}", f"~{avg_daily * 30:.0f}"],
        ["Yearly",  f"${projections.get('yearly_usd', 0):.4f}",  f"~{avg_daily * 365:.0f}"],
    ]

    proj_table = Table(proj_data, colWidths=[w * 0.35, w * 0.35, w * 0.3])
    proj_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0), (-1, 0), GREEN),
        ("TEXTCOLOR",     (0, 0), (-1, 0), WHITE),
        ("FONTNAME",      (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME",      (0, 1), (1, -1), "Helvetica-Bold"),
        ("TEXTCOLOR",     (1, 1), (1, -1), GREEN),
        ("FONTSIZE",      (0, 0), (-1, -1), 11),
        ("ROWBACKGROUNDS",(0, 1), (-1, -1), [WHITE, GREEN_LIGHT]),
        ("ALIGN",         (1, 0), (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("GRID",          (0, 0), (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story.append(proj_table)
    story.append(Spacer(1, 0.6 * cm))

    story.append(_section_header("Cost Breakdown by Agent", w))
    story.append(Spacer(1, 0.3 * cm))

    breakdown_data = [
        ["Agent", "Cost/Ticket", "% of Total", "Model"],
        ["Classification Agent", "$0.0002", "6.5%",  "Claude Haiku 4.5"],
        ["Sentiment Agent",      "$0.0003", "9.7%",  "Claude Haiku 4.5"],
        ["Knowledge Agent",      "$0.0000", "0%",    "Local RAG"],
        ["Response Agent",       "$0.0012", "38.7%", "Claude Haiku 4.5"],
        ["Quality Evaluator",    "$0.0012", "38.7%", "Claude Sonnet 4.6"],
        ["Summary Agent",        "$0.0002", "6.5%",  "Claude Haiku 4.5"],
        ["TOTAL",                "$0.0031", "100%",  ""],
    ]

    breakdown_table = Table(breakdown_data, colWidths=[w * 0.35, w * 0.2, w * 0.2, w * 0.25])
    breakdown_table.setStyle(TableStyle([
        ("BACKGROUND",    (0, 0),  (-1, 0),  GRAY_DARK),
        ("TEXTCOLOR",     (0, 0),  (-1, 0),  WHITE),
        ("FONTNAME",      (0, 0),  (-1, 0),  "Helvetica-Bold"),
        ("BACKGROUND",    (0, -1), (-1, -1), GRAY_DARK),
        ("TEXTCOLOR",     (0, -1), (-1, -1), WHITE),
        ("FONTNAME",      (0, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE",      (0, 0),  (-1, -1), 10),
        ("ROWBACKGROUNDS",(0, 1),  (-1, -2), [WHITE, PURPLE_LIGHT]),
        ("ALIGN",         (1, 0),  (-1, -1), "CENTER"),
        ("VALIGN",        (0, 0),  (-1, -1), "MIDDLE"),
        ("TOPPADDING",    (0, 0),  (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0),  (-1, -1), 8),
        ("GRID",          (0, 0),  (-1, -1), 0.5, colors.HexColor("#E5E7EB")),
    ]))
    story.append(breakdown_table)

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)

    buffer.seek(0)
    return buffer
