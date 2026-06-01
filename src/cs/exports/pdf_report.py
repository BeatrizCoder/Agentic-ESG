"""Climate Sentinel — PDF report generator (reportlab)."""

import logging
from datetime import datetime
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

logger = logging.getLogger(__name__)

# ── Brand palette ─────────────────────────────────────────────────────────────
NAVY     = colors.HexColor("#0d1117")
TEAL     = colors.HexColor("#2e7d9a")
TEAL_LT  = colors.HexColor("#4aa8c8")
OFFWHT   = colors.HexColor("#e8ede8")
MUTED    = colors.HexColor("#6a8898")
WHITE    = colors.white
BORDER   = colors.HexColor("#1a2636")

RISK_COLORS = {
    "low":      (colors.HexColor("#0d2218"), colors.HexColor("#3aaa78")),
    "medium":   (colors.HexColor("#221c08"), colors.HexColor("#c4ae3a")),
    "high":     (colors.HexColor("#221208"), colors.HexColor("#c46a2a")),
    "critical": (colors.HexColor("#220808"), colors.HexColor("#c42a2a")),
}
# Plain hex strings for use inside Paragraph markup (reportlab <font color='#rrggbb'>)
RISK_HEX_FG = {
    "low": "#3aaa78", "medium": "#c4ae3a", "high": "#c46a2a", "critical": "#c42a2a",
}
FW_HEX = {
    "CSRD": "#4aa8c8", "ISSB_S2": "#d4b84a", "EU_TAXONOMY": "#3aaa78", "OPERATIONAL": "#6a8898",
}
FW_COLORS = {k: colors.HexColor(v) for k, v in FW_HEX.items()}
COMP_HEX_FG = {
    "low": "#3aaa78", "medium": "#c4ae3a", "high": "#c46a2a", "critical": "#c42a2a",
    "partial": "#c4ae3a", "misaligned": "#c42a2a", "aligned": "#3aaa78", "not_assessed": "#6a8898",
}


def _styles() -> dict:
    return {
        "h1": ParagraphStyle("h1", fontSize=22, fontName="Helvetica-Bold",
                              textColor=WHITE, spaceAfter=2),
        "h2": ParagraphStyle("h2", fontSize=11, fontName="Helvetica-Bold",
                              textColor=TEAL_LT, spaceAfter=6, spaceBefore=14),
        "sub": ParagraphStyle("sub", fontSize=9, fontName="Helvetica",
                               textColor=MUTED, spaceAfter=2),
        "body": ParagraphStyle("body", fontSize=9, fontName="Helvetica",
                                textColor=colors.HexColor("#1a2a2a"),
                                leading=14, spaceAfter=4),
        "mono": ParagraphStyle("mono", fontSize=8, fontName="Courier",
                                textColor=colors.HexColor("#2a3a4a")),
        "cell": ParagraphStyle("cell", fontSize=8, fontName="Helvetica",
                                textColor=colors.HexColor("#1a2a2a"), leading=11),
        "cell_bold": ParagraphStyle("cell_bold", fontSize=8, fontName="Helvetica-Bold",
                                     textColor=colors.HexColor("#1a2a2a")),
        "footer": ParagraphStyle("footer", fontSize=7, fontName="Helvetica",
                                  textColor=MUTED, alignment=TA_RIGHT),
    }


def _header_footer(canvas, doc):
    canvas.saveState()
    w, _ = A4
    canvas.setStrokeColor(colors.HexColor("#2e7d9a"))
    canvas.setLineWidth(0.4)
    canvas.line(2 * cm, 1.6 * cm, w - 2 * cm, 1.6 * cm)
    canvas.setFont("Helvetica", 7)
    canvas.setFillColor(MUTED)
    canvas.drawString(2 * cm, 1.2 * cm, "Climate Sentinel · ESG Intelligence — Confidential")
    canvas.drawRightString(
        w - 2 * cm, 1.2 * cm,
        f"Page {doc.page} · {datetime.utcnow().strftime('%d %b %Y')}",
    )
    canvas.restoreState()


def generate_pdf(analysis: dict) -> BytesIO:
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2.2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
    )

    S = _styles()
    w_full = A4[0] - 4 * cm
    story = []

    # ── Cover band ────────────────────────────────────────────────────────────
    risk_level = analysis.get("risk_level", "low")
    _, risk_fg = RISK_COLORS.get(risk_level, RISK_COLORS["low"])

    cover = Table(
        [[
            Paragraph("ClimateSentinel", S["h1"]),
            Paragraph(
                "<font color='" + RISK_HEX_FG.get(risk_level, "#6a8898") + "'>ESG Intelligence</font>",
                ParagraphStyle("tag", fontSize=8, fontName="Helvetica",
                               textColor=MUTED, alignment=TA_RIGHT),
            ),
        ]],
        colWidths=[w_full * .7, w_full * .3],
    )
    cover.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), NAVY),
        ("TOPPADDING",  (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
        ("LEFTPADDING",  (0, 0), (0, -1), 14),
        ("RIGHTPADDING", (-1, 0), (-1, -1), 14),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ROUNDEDCORNERS", [6]),
    ]))
    story.append(cover)
    story.append(Spacer(1, 10))

    # ── Meta row ──────────────────────────────────────────────────────────────
    region   = analysis.get("region_label", "—")
    lat, lon = analysis.get("latitude", 0), analysis.get("longitude", 0)
    aid      = analysis.get("analysis_id", "—")
    created  = analysis.get("created_at", "")[:10]
    duration = analysis.get("pipeline_duration_sec", 0)

    meta = Table(
        [[
            Paragraph(f"<b>{region}</b>", S["cell_bold"]),
            Paragraph(f"{lat:.4f}, {lon:.4f}", S["mono"]),
            Paragraph(aid, S["mono"]),
            Paragraph(created, S["mono"]),
        ]],
        colWidths=[w_full * .35, w_full * .2, w_full * .25, w_full * .2],
    )
    meta.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#f4f6f4")),
        ("BOX",          (0, 0), (-1, -1), 0.4, colors.HexColor("#d0dce0")),
        ("TOPPADDING",   (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 7),
        ("LEFTPADDING",  (0, 0), (-1, -1), 8),
    ]))
    story.append(meta)
    story.append(Spacer(1, 12))

    # ── Risk score ────────────────────────────────────────────────────────────
    story.append(Paragraph("CLIMATE RISK SCORE", S["h2"]))
    score      = analysis.get("risk_score", 0)
    badge      = analysis.get("risk_badge_label", risk_level.upper() + " RISK")
    risk_bg, risk_fg = RISK_COLORS.get(risk_level, RISK_COLORS["low"])

    score_table = Table(
        [[
            Paragraph(f"<b>{score}</b>/100", ParagraphStyle(
                "score", fontSize=28, fontName="Helvetica-Bold",
                textColor=colors.HexColor("#1a2a2a"))),
            Paragraph(badge, ParagraphStyle(
                "badge", fontSize=10, fontName="Helvetica-Bold",
                textColor=risk_fg, alignment=TA_CENTER)),
        ]],
        colWidths=[w_full * .25, w_full * .35],
    )
    score_table.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (0, -1), colors.HexColor("#f4f6f4")),
        ("BACKGROUND",   (1, 0), (1, -1), risk_bg),
        ("BOX",          (0, 0), (0, -1), 0.4, colors.HexColor("#d0dce0")),
        ("BOX",          (1, 0), (1, -1), 0.8, risk_fg),
        ("TOPPADDING",   (0, 0), (-1, -1), 12),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 12),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("VALIGN",       (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(score_table)
    story.append(Spacer(1, 12))

    # ── Key metrics ───────────────────────────────────────────────────────────
    km = analysis.get("key_metrics", {})
    if km:
        story.append(Paragraph("KEY METRICS", S["h2"]))
        metrics_data = [
            ["Temperature Change", km.get("temp_change_label", "—")],
            ["Precipitation Change", km.get("precip_change_label", "—")],
            ["Compliance Exposure", km.get("compliance_exposure_label", "—")],
            ["Hottest Year", str(km.get("hottest_year", "—"))],
            ["Driest Year",  str(km.get("driest_year", "—"))],
        ]
        metrics_table = Table(
            [[Paragraph(k, S["cell_bold"]), Paragraph(v, S["mono"])]
             for k, v in metrics_data],
            colWidths=[w_full * .4, w_full * .6],
        )
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND",   (0, 0), (-1, -1), colors.HexColor("#f9fbfc")),
            ("ROWBACKGROUNDS", (0, 0), (-1, -1),
             [colors.HexColor("#f4f6f4"), colors.white]),
            ("BOX",          (0, 0), (-1, -1), 0.4, colors.HexColor("#d0dce0")),
            ("INNERGRID",    (0, 0), (-1, -1), 0.2, colors.HexColor("#d0dce0")),
            ("TOPPADDING",   (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
            ("LEFTPADDING",  (0, 0), (-1, -1), 8),
        ]))
        story.append(metrics_table)
        story.append(Spacer(1, 12))

    # ── Executive summary ─────────────────────────────────────────────────────
    summary = analysis.get("executive_summary", "")
    if summary:
        story.append(Paragraph("EXECUTIVE SUMMARY", S["h2"]))
        story.append(Paragraph(summary, S["body"]))
        story.append(Spacer(1, 8))

    # ── Compliance mapping ────────────────────────────────────────────────────
    comp = analysis.get("compliance_mapping", {})
    if comp:
        story.append(Paragraph("COMPLIANCE FRAMEWORK MAPPING", S["h2"]))
        comp_items = [
            ("CSRD",        comp.get("csrd_exposure","—"),      comp.get("csrd_summary",""),      comp.get("csrd_articles",[])),
            ("ISSB S2",     comp.get("issb_s2_exposure","—"),   comp.get("issb_s2_summary",""),   comp.get("issb_s2_scenarios",[])),
            ("EU TAXONOMY", comp.get("eu_taxonomy_alignment","—"), comp.get("eu_taxonomy_summary",""), comp.get("eu_taxonomy_criteria",[])),
        ]
        _clr = {"low":"#3aaa78","medium":"#c4ae3a","high":"#c46a2a","critical":"#c42a2a",
                "partial":"#c4ae3a","misaligned":"#c42a2a","aligned":"#3aaa78","not_assessed":"#6a8898"}
        comp_rows = [
            [Paragraph("<b>Framework</b>", S["cell_bold"]),
             Paragraph("<b>Exposure</b>",  S["cell_bold"]),
             Paragraph("<b>Summary</b>",   S["cell_bold"]),
             Paragraph("<b>Key Articles</b>", S["cell_bold"])],
        ]
        for fw, exp, summ, arts in comp_items:
            fg_hex = COMP_HEX_FG.get(exp, "#6a8898")
            comp_rows.append([
                Paragraph(fw, S["cell_bold"]),
                Paragraph(f"<font color='{fg_hex}'><b>{exp.upper()}</b></font>", S["cell"]),
                Paragraph(summ, S["cell"]),
                Paragraph(", ".join((arts or [])[:3]), S["cell"]),
            ])
        comp_table = Table(comp_rows, colWidths=[w_full*.13, w_full*.12, w_full*.42, w_full*.33])
        comp_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#e8eef2")),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f4f8fa"), colors.white]),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d0dce0")),
            ("INNERGRID",     (0, 0), (-1, -1), 0.2, colors.HexColor("#d0dce0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(comp_table)
        story.append(Spacer(1, 12))

    # ── Recommendations ───────────────────────────────────────────────────────
    recs = analysis.get("recommendations", [])
    if recs:
        story.append(Paragraph("PRIORITISED RECOMMENDATIONS", S["h2"]))
        rec_rows = [
            [Paragraph("<b>#</b>",         S["cell_bold"]),
             Paragraph("<b>Framework</b>", S["cell_bold"]),
             Paragraph("<b>Action</b>",    S["cell_bold"]),
             Paragraph("<b>Article</b>",   S["cell_bold"]),
             Paragraph("<b>Timeline</b>",  S["cell_bold"])],
        ]
        for r in recs:
            fw      = r.get("framework", "")
            fw_hex  = FW_HEX.get(fw, "#6a8898")
            rec_rows.append([
                Paragraph(f"<b>{r.get('rank','')}</b>", S["cell_bold"]),
                Paragraph(f"<font color='{fw_hex}'><b>{fw}</b></font>", S["cell"]),
                Paragraph(r.get("action", ""), S["cell"]),
                Paragraph(r.get("article", ""), S["cell"]),
                Paragraph((r.get("timeline","")).replace("_"," "), S["cell"]),
            ])
        rec_table = Table(
            rec_rows,
            colWidths=[w_full*.05, w_full*.14, w_full*.52, w_full*.17, w_full*.12],
        )
        rec_table.setStyle(TableStyle([
            ("BACKGROUND",    (0, 0), (-1, 0),  colors.HexColor("#e8eef2")),
            ("ROWBACKGROUNDS",(0, 1), (-1, -1), [colors.HexColor("#f4f8fa"), colors.white]),
            ("BOX",           (0, 0), (-1, -1), 0.5, colors.HexColor("#d0dce0")),
            ("INNERGRID",     (0, 0), (-1, -1), 0.2, colors.HexColor("#d0dce0")),
            ("TOPPADDING",    (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("LEFTPADDING",   (0, 0), (-1, -1), 6),
            ("VALIGN",        (0, 0), (-1, -1), "TOP"),
        ]))
        story.append(rec_table)

    # ── Privacy note ──────────────────────────────────────────────────────────
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        f"Generated by Climate Sentinel · {datetime.utcnow().strftime('%d %b %Y %H:%M')} UTC · "
        "Session data stored as temporary cookie only. No personal data collected or retained.",
        S["footer"],
    ))

    doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
    buf.seek(0)
    logger.info("PDF generated for analysis %s", analysis.get("analysis_id"))
    return buf
