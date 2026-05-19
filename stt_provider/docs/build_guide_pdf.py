"""
Generate the step-by-step PDF guide from the strategy doc.

This script uses ReportLab to create a professionally formatted PDF guide
that transforms the strategy documentation into an actionable step-by-step
implementation guide. The PDF includes styled headings, step cards, tables,
and callouts with a consistent visual design.

Run this from anywhere; it writes the PDF next to itself:
    pip install reportlab
    python build_guide_pdf.py

Or just double-click `build_guide_pdf.bat` on Windows.

The generated PDF includes:
- Cover page with title and subtitle
- Phase-based implementation steps (Phase 0-4)
- Architecture decision tables
- Step cards with effort estimates
- Callout boxes for important notes
- Page headers with page numbers
"""
from __future__ import annotations

import logging
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


OUT_PATH = Path(__file__).resolve().parent / "step-by-step-guide.pdf"


# -------- styles --------

styles = getSampleStyleSheet()

INK = colors.HexColor("#1f2937")
ACCENT = colors.HexColor("#2563eb")
MUTED = colors.HexColor("#6b7280")
RULE = colors.HexColor("#e5e7eb")
BG_TABLE_HEADER = colors.HexColor("#1f2937")
BG_TABLE_ALT = colors.HexColor("#f3f4f6")

title_style = ParagraphStyle(
    "TitleBig", parent=styles["Title"],
    fontName="Helvetica-Bold", fontSize=26, leading=32,
    textColor=INK, spaceAfter=8, alignment=TA_LEFT,
)
subtitle_style = ParagraphStyle(
    "Subtitle", parent=styles["Normal"],
    fontName="Helvetica", fontSize=13, leading=17,
    textColor=MUTED, spaceAfter=18,
)
h1_style = ParagraphStyle(
    "H1", parent=styles["Heading1"],
    fontName="Helvetica-Bold", fontSize=18, leading=22,
    textColor=ACCENT, spaceBefore=18, spaceAfter=10, keepWithNext=True,
)
h2_style = ParagraphStyle(
    "H2", parent=styles["Heading2"],
    fontName="Helvetica-Bold", fontSize=14, leading=18,
    textColor=INK, spaceBefore=14, spaceAfter=6, keepWithNext=True,
)
h3_style = ParagraphStyle(
    "H3", parent=styles["Heading3"],
    fontName="Helvetica-Bold", fontSize=11, leading=15,
    textColor=INK, spaceBefore=10, spaceAfter=4, keepWithNext=True,
)
body_style = ParagraphStyle(
    "Body", parent=styles["BodyText"],
    fontName="Helvetica", fontSize=10.5, leading=15,
    textColor=INK, spaceAfter=6,
)
muted_style = ParagraphStyle(
    "Muted", parent=body_style,
    textColor=MUTED, fontSize=9.5, leading=13,
)
step_label_style = ParagraphStyle(
    "StepLabel", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=10.5, leading=14,
    textColor=ACCENT,
)
step_title_style = ParagraphStyle(
    "StepTitle", parent=styles["Normal"],
    fontName="Helvetica-Bold", fontSize=11.5, leading=15,
    textColor=INK, spaceAfter=2,
)
step_body_style = ParagraphStyle(
    "StepBody", parent=body_style,
    fontSize=10, leading=14, spaceAfter=4,
)
callout_style = ParagraphStyle(
    "Callout", parent=body_style,
    fontName="Helvetica-Oblique", fontSize=10, leading=14,
    leftIndent=10, rightIndent=10, spaceBefore=4, spaceAfter=8,
    textColor=INK,
)
code_style = ParagraphStyle(
    "Code", parent=body_style,
    fontName="Courier", fontSize=9.5, leading=13, leftIndent=10,
    textColor=INK, spaceAfter=8,
)


# -------- helpers --------

def page_chrome(canvas_obj, doc):
    """
    Add header rule and page number to every page after the cover.
    
    Draws a horizontal rule near the top of each page (except the cover),
    displays the document title on the left, and shows the page number
    on the right.
    
    Args:
        canvas_obj: ReportLab canvas object for drawing
        doc: Document object containing page information
    """
    canvas_obj.saveState()
    if doc.page > 1:
        canvas_obj.setStrokeColor(RULE)
        canvas_obj.setLineWidth(0.5)
        canvas_obj.line(
            doc.leftMargin, doc.pagesize[1] - 0.55 * inch,
            doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - 0.55 * inch,
        )
        canvas_obj.setFont("Helvetica", 8.5)
        canvas_obj.setFillColor(MUTED)
        canvas_obj.drawString(
            doc.leftMargin, doc.pagesize[1] - 0.42 * inch,
            "Streaming STT Platform — Step-by-Step Guide",
        )
        canvas_obj.drawRightString(
            doc.pagesize[0] - doc.rightMargin, doc.pagesize[1] - 0.42 * inch,
            f"Page {doc.page}",
        )
    canvas_obj.restoreState()


def callout(text: str):
    """
    Create a callout box with highlighted text.
    
    Renders a callout box with a light blue background and an accent border
    on the left side. Used for important notes, warnings, or emphasis.
    
    Args:
        text: The text content to display in the callout
        
    Returns:
        Table object styled as a callout box
    """
    box = Table(
        [[Paragraph(text, callout_style)]],
        colWidths=[6.5 * inch],
    )
    box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ("LINEBEFORE", (0, 0), (0, -1), 2, ACCENT),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    return box


def step(num: int, title: str, body_lines: list[str], time_estimate: str | None = None):
    """
    Create a numbered step card with title, body, and optional effort estimate.
    
    Renders a step card with a step number, title, body text lines, and an
    optional effort estimate. The card has a bordered design with an accent
    line on the left.
    
    Args:
        num: Step number to display
        title: Step title
        body_lines: List of body text lines
        time_estimate: Optional effort estimate string
        
    Returns:
        Table object styled as a step card
    """
    rows = [[Paragraph(f"Step {num}", step_label_style),
             Paragraph(title, step_title_style)]]
    for line in body_lines:
        rows.append(["", Paragraph(line, step_body_style)])
    if time_estimate:
        rows.append(["", Paragraph(
            f"<font color='#6b7280'><b>Effort:</b> {time_estimate}</font>",
            step_body_style,
        )])

    tbl = Table(rows, colWidths=[0.85 * inch, 5.65 * inch])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.white),
        ("LINEABOVE", (0, 0), (-1, 0), 0.5, RULE),
        ("LINEBELOW", (0, -1), (-1, -1), 0.5, RULE),
        ("LINEBEFORE", (0, 0), (0, -1), 3, ACCENT),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    return tbl


def info_table(rows: list[list[str]], col_widths: list[float], header: bool = True):
    """
    Create an information table with optional header row.
    
    Renders a table with styled cells, optional header row with dark background,
    and alternating row colors for readability.
    
    Args:
        rows: List of table rows, each row is a list of cell strings
        col_widths: List of column widths in inches
        header: Whether to style the first row as a header (default: True)
        
    Returns:
        Table object styled with header and alternating row colors
    """
    table_rows: list[list] = []
    for r_idx, row in enumerate(rows):
        style_row = []
        for c_idx, cell in enumerate(row):
            is_header = header and r_idx == 0
            sty = ParagraphStyle(
                f"cell_{r_idx}_{c_idx}", parent=body_style,
                fontSize=9.5, leading=13,
                fontName="Helvetica-Bold" if is_header else "Helvetica",
                textColor=colors.white if is_header else INK,
            )
            style_row.append(Paragraph(cell, sty))
        table_rows.append(style_row)

    tbl = Table(table_rows, colWidths=col_widths, repeatRows=1 if header else 0)
    cmds = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.4, RULE),
    ]
    if header:
        cmds.append(("BACKGROUND", (0, 0), (-1, 0), BG_TABLE_HEADER))
        for r_idx in range(2, len(rows), 2):
            cmds.append(("BACKGROUND", (0, r_idx), (-1, r_idx), BG_TABLE_ALT))
    tbl.setStyle(TableStyle(cmds))
    return tbl


# -------- content --------

def build_story():
    """
    Build the PDF story content for the step-by-step guide.
    
    Constructs the complete PDF content including cover page, phase sections,
    step cards, tables, and callouts. Returns a list of flowable objects
    that can be rendered by ReportLab.
    
    Returns:
        List of flowable objects for PDF generation
    """
    logger.info("Building PDF story content")
    s: list = []

    # Cover
    s.append(Spacer(1, 1.4 * inch))
    s.append(Paragraph("Step-by-Step Guide", title_style))
    s.append(Paragraph(
        "Building a max-quality streaming Speech-to-Text platform — latency, "
        "managed scaling, diarization, enterprise reliability, accuracy tuning.",
        subtitle_style,
    ))
    s.append(Spacer(1, 0.4 * inch))
    s.append(Paragraph(
        "<b>Source repo:</b> <font color='#2563eb'>true-streaming-stt-provider</font>",
        body_style,
    ))
    s.append(Paragraph(
        "<b>Companion docs:</b> README.md, docs/streaming-design.md, "
        "docs/maximize-each-category.md",
        body_style,
    ))
    s.append(Paragraph(
        "<b>Prepared:</b> May 2026",
        body_style,
    ))
    s.append(Spacer(1, 0.45 * inch))
    s.append(callout(
        "This guide turns the strategy doc into an actionable sequence. Phase 0 "
        "decides which path you take; everything after Phase 1 forks into a "
        "cloud-first track (Phase 2A) and a self-hosted track (Phase 2B). "
        "Pick one. Pick both later if you need a hybrid."
    ))

    # Architecture choice overview
    s.append(Spacer(1, 0.3 * inch))
    s.append(Paragraph("How to use this guide", h2_style))
    s.append(Paragraph(
        "Each phase below is a sequence of numbered steps. A step lists what "
        "to do, what to deliver, and a rough effort estimate for a 2–3 "
        "engineer team. Steps within a phase are sequential. Phases overlap: "
        "Phase 1 can run in parallel with Phase 0 once the decision is made, "
        "and Phase 3 (hardening) can start in parallel with Phase 2.",
        body_style,
    ))
    s.append(Paragraph(
        "If you only read one thing: do every step in Phase 1 regardless of "
        "which long-term path you pick.",
        body_style,
    ))

    s.append(PageBreak())

    # -------- Phase 0 --------
    s.append(Paragraph("Phase 0 · Strategic decision", h1_style))
    s.append(Paragraph("Week 0 · 1 week · ~1 engineer", muted_style))
    s.append(Paragraph(
        "Before any code lands, decide the customer profile, the compliance "
        "ceiling, and the hosting path. The rest of this guide branches "
        "based on these answers.",
        body_style,
    ))

    s.append(step(
        1, "Profile your target customer",
        [
            "Who is the user — voice agents, meeting transcription, contact "
            "center, healthcare scribe, broadcast captioning? Latency budgets "
            "and diarization requirements differ by 5–10× across these.",
            "Write down: peak concurrent streams, P50 latency target, P95 "
            "latency target, max session duration, and average audio minutes "
            "per tenant per month.",
        ],
        "0.5 day",
    ))

    s.append(step(
        2, "Set your compliance ceiling",
        [
            "Pick the highest bar you will need within 18 months: SOC 2 "
            "Type II only, or HIPAA BAA, or ISO 27001, or FedRAMP Moderate.",
            "This decides whether enterprise-reliability work (Phase 3) is a "
            "stretch goal or a launch blocker.",
        ],
        "0.5 day",
    ))

    s.append(step(
        3, "Choose the hosting path",
        [
            "<b>Cloud-first:</b> proxy to Deepgram + pyannoteAI. Six to ten "
            "weeks to 'max each'. Best for small teams. Trades data residency.",
            "<b>Self-hosted:</b> NVIDIA Riva on GPU Kubernetes. Six to nine "
            "months. Best for compliance-bound or fine-tuning-heavy customers.",
            "<b>Hybrid:</b> both backends behind one gateway, per-tenant "
            "routing. Nine to twelve months. The right end state if you have "
            "tenants on both sides of the fence.",
        ],
        "2–3 days",
    ))

    s.append(step(
        4, "Write the architecture decision record",
        [
            "Single page. Customer profile, latency targets, compliance bar, "
            "chosen path, two reasonable alternatives, and the trade-offs you "
            "accepted. This becomes the document every engineer refers to "
            "when scope creeps.",
        ],
        "0.5 day",
    ))

    s.append(Spacer(1, 0.2 * inch))
    s.append(callout(
        "Deliverable: a 1-page ADR committed to the repo at "
        "<font name='Courier'>docs/adr/0001-architecture.md</font>."
    ))

    s.append(PageBreak())

    # -------- Phase 1 --------
    s.append(Paragraph("Phase 1 · Quick wins on the current stack", h1_style))
    s.append(Paragraph("Weeks 1–2 · ~1–2 engineers", muted_style))
    s.append(Paragraph(
        "Every step below applies regardless of which long-term path you "
        "chose in Phase 0. They turn the current single-server FastAPI app "
        "into something safer, faster, and easier to operate without "
        "changing its architecture.",
        body_style,
    ))

    s.append(step(
        1, "Eliminate the dev API-key default",
        [
            "In <font name='Courier'>stt_server/config.py</font>, keep "
            "<font name='Courier'>stt_api_key: str = ''</font> as the default "
            "so keys must be configured explicitly.",
            "In <font name='Courier'>main.py</font>'s lifespan, "
            "<font name='Courier'>raise RuntimeError(...)</font> if "
            "<font name='Courier'>settings.stt_api_key</font> is empty and "
            "<font name='Courier'>ENV</font> is anything other than 'dev'.",
            "Update <font name='Courier'>.env.example</font> and the README "
            "deployment section to require an explicit value.",
        ],
        "2 hours",
    ))

    s.append(step(
        2, "Drop the temp-WAV round trip",
        [
            "In <font name='Courier'>stt_server/model.py</font>, accept a "
            "NumPy float32 array directly: "
            "<font name='Courier'>WhisperModel.transcribe(np_array, ...)</font>.",
            "In <font name='Courier'>streaming.py</font>, convert the PCM-16LE "
            "<font name='Courier'>bytes</font> to "
            "<font name='Courier'>np.frombuffer(...).astype(np.float32) / "
            "32768.0</font> instead of writing a WAV.",
            "Measure before/after: time-to-partial should drop 30–50 ms.",
        ],
        "0.5 day",
    ))

    s.append(step(
        3, "Expose decoder knobs end-to-end",
        [
            "Add optional query params to <font name='Courier'>WS "
            "/stt/stream</font>: <font name='Courier'>hotwords</font> "
            "(comma-separated), <font name='Courier'>initial_prompt</font>, "
            "<font name='Courier'>beam_size</font>, "
            "<font name='Courier'>word_timestamps</font>, "
            "<font name='Courier'>temperature</font>.",
            "Same parameters on <font name='Courier'>POST /v1/audio/"
            "transcriptions</font> as form fields.",
            "Pass them through to <font name='Courier'>WhisperModel."
            "transcribe(...)</font>. Whisper's "
            "<font name='Courier'>hotwords</font> is available in "
            "faster-whisper ≥ 1.0.",
        ],
        "1 day",
    ))

    s.append(step(
        4, "Rate limit the REST endpoints",
        [
            "Add <font name='Courier'>slowapi</font> or "
            "<font name='Courier'>fastapi-limiter</font>. Key the limit on "
            "the API key (not on IP).",
            "Conservative defaults: 30 transcriptions/minute and 5 admin "
            "calls/minute per key. Expose the limit in admin config so "
            "tenant tiers can override.",
        ],
        "0.5 day",
    ))

    s.append(step(
        5, "Structured logging with trace IDs",
        [
            "Replace the JSON line writer in "
            "<font name='Courier'>logging_utils.py</font> with "
            "<font name='Courier'>structlog</font> or stdlib JSON.",
            "Generate a trace ID per WebSocket session and per HTTP request. "
            "Include it in every log line and surface it in error responses "
            "via an <font name='Courier'>X-Trace-Id</font> header.",
            "Wire up OpenTelemetry: traces export to OTLP, customer "
            "controls the collector endpoint.",
        ],
        "1 day",
    ))

    s.append(step(
        6, "Cache the API-key map",
        [
            "<font name='Courier'>auth.get_api_key_map()</font> currently "
            "reparses settings on every request. Wrap it in "
            "<font name='Courier'>functools.lru_cache(maxsize=1)</font> with "
            "a TTL invalidation when keys change.",
            "If you wire in a hashed-key store later, this is the seam.",
        ],
        "1 hour",
    ))

    s.append(step(
        7, "Ship Phase 1 and measure",
        [
            "Cut a release tag (<font name='Courier'>v0.2.0</font>).",
            "Capture a baseline: P50/P95 time-to-first-partial, P50/P95 "
            "time-between-partials, WER on a fixed test set with and "
            "without hotwords.",
            "These numbers become the bar Phase 2 has to beat.",
        ],
        "0.5 day",
    ))

    s.append(PageBreak())

    # -------- Phase 2 fork --------
    s.append(Paragraph("Phase 2 · Pick a path", h1_style))
    s.append(Paragraph(
        "Two backends, same gateway protocol on the outside. Do 2A if Phase "
        "0 said cloud-first or hybrid. Do 2B if Phase 0 said self-hosted or "
        "hybrid. For hybrid, do them in parallel with separate teams.",
        body_style,
    ))

    s.append(Spacer(1, 0.2 * inch))
    s.append(info_table(
        rows=[
            ["", "Phase 2A — Cloud-first", "Phase 2B — Self-hosted"],
            ["Timeline", "3–6 weeks", "8–12 weeks"],
            ["Team", "1–2 engineers", "3–5 engineers + ML platform"],
            ["P50 latency", "Sub-300 ms (Deepgram Flux)", "300–500 ms (Parakeet on Riva)"],
            ["Diarization", "pyannoteAI Precision-2", "NVIDIA Sortformer"],
            ["Custom vocab", "Deepgram Keyterm Prompting", "NeMo fine-tuning + word boost"],
            ["Per-minute cost", "$0.005–0.02 (Deepgram + pyannoteAI)", "Fixed GPU rental"],
            ["Data residency", "US/EU regions only", "Full"],
            ["Vendor lock-in", "High", "Low"],
        ],
        col_widths=[1.4 * inch, 2.55 * inch, 2.55 * inch],
    ))

    s.append(PageBreak())

    # -------- Phase 2A --------
    s.append(Paragraph("Phase 2A · Cloud-first path", h1_style))
    s.append(Paragraph("Weeks 3–8 · ~1–2 engineers", muted_style))
    s.append(Paragraph(
        "Replace the model layer with a proxy to Deepgram (STT) and "
        "pyannoteAI (diarization). Keep the existing WebSocket protocol on "
        "the client side; transform on the way in and out.",
        body_style,
    ))

    s.append(step(
        1, "Provision provider accounts",
        [
            "Deepgram: production account, Nova-3 or Flux access, region "
            "matching your customer base (US-East and EU-West are the usual "
            "starting pair).",
            "pyannoteAI: production account, Precision-2 access. Store both "
            "API keys in your secrets manager (not in env files).",
        ],
        "1 day",
    ))

    s.append(step(
        2, "Build the proxy gateway",
        [
            "New module: "
            "<font name='Courier'>stt_server/backends/deepgram.py</font>. "
            "Opens a Deepgram WebSocket, forwards customer audio, translates "
            "Deepgram events back into your event schema.",
            "Keep your existing <font name='Courier'>WS /stt/stream</font> "
            "handler; swap the inner "
            "<font name='Courier'>StreamingTranscriptionSession</font> for a "
            "<font name='Courier'>DeepgramSession</font> behind a feature "
            "flag (<font name='Courier'>STT_BACKEND=deepgram|whisper</font>).",
        ],
        "1 week",
    ))

    s.append(step(
        3, "Translate the event schema",
        [
            "Deepgram emits <font name='Courier'>Results</font> messages with "
            "<font name='Courier'>is_final</font> and "
            "<font name='Courier'>speech_final</font>. Map "
            "<font name='Courier'>is_final=false</font> → "
            "<font name='Courier'>transcript.partial</font>, "
            "<font name='Courier'>speech_final=true</font> → "
            "<font name='Courier'>transcript.final</font>.",
            "Add word-level timestamps and confidences to your event schema "
            "now — you'll need them in step 4.",
        ],
        "2 days",
    ))

    s.append(step(
        4, "Wire up pyannoteAI orchestration",
        [
            "pyannoteAI offers an STT orchestration endpoint that pairs "
            "diarization with the transcription backend of your choice. "
            "Point it at Deepgram and forward customer audio through it.",
            "Add the <font name='Courier'>diarization.revise</font> event "
            "type (suggested in the strategy doc) so the client can update "
            "earlier speaker labels.",
        ],
        "1 week",
    ))

    s.append(step(
        5, "Per-tenant keyterm pass-through",
        [
            "Store per-tenant keyterms in a small Postgres table or KV store. "
            "On WebSocket open, look up the tenant's keyterms and forward "
            "them to Deepgram in the connection URL.",
            "Cap at 100 terms per tenant (Deepgram's limit). Expose a "
            "<font name='Courier'>PUT /v1/tenants/me/keyterms</font> "
            "endpoint for self-service.",
        ],
        "3 days",
    ))

    s.append(step(
        6, "Load test and cut over",
        [
            "Synthetic load: 100 concurrent streams, 8-hour soak. Compare "
            "latency distribution against the Phase 1 baseline.",
            "Roll the feature flag forward in 10% increments per customer "
            "tier. Keep the Whisper path live as a fallback for two weeks "
            "before retiring it.",
        ],
        "1 week",
    ))

    s.append(PageBreak())

    # -------- Phase 2B --------
    s.append(Paragraph("Phase 2B · Self-hosted path", h1_style))
    s.append(Paragraph("Weeks 3–14 · ~3–5 engineers", muted_style))
    s.append(Paragraph(
        "Stand up the production-grade self-hosted stack: NVIDIA Triton "
        "serving Parakeet streaming + Sortformer streaming diarization on a "
        "GPU Kubernetes cluster, with state externalized to Postgres and Redis.",
        body_style,
    ))

    s.append(step(
        1, "Provision GPU Kubernetes",
        [
            "EKS / GKE / AKS with an NVIDIA-GPU node pool (L4 for cost, A10G "
            "for balance, H100 for top latency). Install the NVIDIA device "
            "plugin and DCGM exporter for GPU metrics.",
            "Reserve capacity: streaming ASR cannot tolerate eviction. Use "
            "<font name='Courier'>node-pool autoscaler</font> with a minimum "
            "of 2 GPU nodes for HA.",
        ],
        "1 week",
    ))

    s.append(step(
        2, "Deploy Triton with Parakeet streaming",
        [
            "Pull NVIDIA's reference Triton config for "
            "<font name='Courier'>parakeet-tdt-streaming</font> from the NIM "
            "catalog. Deploy as a StatefulSet pinned to GPU nodes.",
            "Triton exposes gRPC; your gateway becomes a thin gRPC client. "
            "Use Triton's dynamic batching with a "
            "<font name='Courier'>max_queue_delay_microseconds</font> tuned "
            "for your latency budget (start at 5 ms).",
        ],
        "2 weeks",
    ))

    s.append(step(
        3, "Add Sortformer streaming diarization",
        [
            "Deploy <font name='Courier'>diar_streaming_sortformer_4spk-v2"
            "</font> alongside Parakeet in the same Triton instance group.",
            "Configure the ASR pipeline so each end-of-utterance gets "
            "speaker tags attached at the word level. Surface as "
            "<font name='Courier'>spk_0..spk_3</font> in your transcript "
            "events.",
        ],
        "1 week",
    ))

    s.append(step(
        4, "Externalize state",
        [
            "Postgres: <font name='Courier'>tenants</font>, "
            "<font name='Courier'>api_keys</font> (hashed), "
            "<font name='Courier'>usage_counters</font>, "
            "<font name='Courier'>audit_log</font>. Replace "
            "<font name='Courier'>logs/usage-snapshot.json</font> with a "
            "transactional table.",
            "Redis: ephemeral counters (active connection gauge per pod, "
            "per-tenant rate limits). <font name='Courier'>INCR</font> on "
            "connect, <font name='Courier'>DECR</font> on disconnect, "
            "<font name='Courier'>EXPIRE</font> as a safety net.",
        ],
        "1 week",
    ))

    s.append(step(
        5, "Connection draining + PodDisruptionBudgets",
        [
            "On <font name='Courier'>SIGTERM</font>: stop accepting new "
            "WebSocket upgrades, flip readiness to false, wait up to "
            "<font name='Courier'>MAX_SESSION_SECONDS</font> for in-flight "
            "sessions to drain, then exit.",
            "PDB: <font name='Courier'>maxUnavailable: 1</font> on the "
            "gateway, <font name='Courier'>minAvailable: 2</font> on Triton. "
            "Set <font name='Courier'>terminationGracePeriodSeconds</font> "
            "to match max session duration.",
        ],
        "3 days",
    ))

    s.append(step(
        6, "KEDA autoscaling",
        [
            "Install KEDA. Define a "
            "<font name='Courier'>ScaledObject</font> for the gateway with "
            "<font name='Courier'>active_websocket_connections</font> "
            "(from Redis) as the trigger.",
            "Separate <font name='Courier'>ScaledObject</font> for Triton "
            "keyed on <font name='Courier'>nv_inference_queue_duration_us"
            "</font> from DCGM.",
            "Define <font name='Courier'>maxReplicaCount</font> headroom = "
            "2× expected peak.",
        ],
        "1 week",
    ))

    s.append(step(
        7, "Load test and cut over",
        [
            "Soak test: 200 concurrent streams for 12 hours. Validate that "
            "rolling pod restarts don't drop active sessions (they will "
            "until step 5 is right — that's the test).",
            "Roll out per tenant tier the same way as Phase 2A. Keep the "
            "Whisper path as a fallback during ramp.",
        ],
        "1 week",
    ))

    s.append(PageBreak())

    # -------- Phase 3 --------
    s.append(Paragraph("Phase 3 · Enterprise hardening", h1_style))
    s.append(Paragraph("Weeks 9–18 · runs in parallel with Phase 2 · ~2 engineers", muted_style))

    s.append(Paragraph(
        "These steps are what auditors actually check. None of them are "
        "exciting; all of them are non-negotiable for enterprise deals.",
        body_style,
    ))

    s.append(step(
        1, "mTLS at the edge",
        [
            "Terminate TLS at Envoy or an equivalent ingress. Optional mTLS "
            "for service-to-service calls into your VPC; required if you "
            "advertise PrivateLink-style connectivity.",
            "Cert-manager + Let's Encrypt for public certs; private CA "
            "(Smallstep, AWS Private CA, Vault) for internal certs.",
        ],
        "1 week",
    ))

    s.append(step(
        2, "SSO / SAML / SCIM for tenant admins",
        [
            "Don't build this yourself — integrate with WorkOS, Auth0, or "
            "Stytch. Three-day integration vs. three-month rebuild.",
            "Enforce SSO at the org level for any tenant on an enterprise "
            "plan. SCIM provisions and deprovisions admin users automatically.",
        ],
        "1 week",
    ))

    s.append(step(
        3, "RBAC scopes on API keys",
        [
            "Scope keys to operations: "
            "<font name='Courier'>stt:stream</font>, "
            "<font name='Courier'>stt:transcribe</font>, "
            "<font name='Courier'>usage:read</font>, "
            "<font name='Courier'>admin:*</font>.",
            "Enforce in middleware before the route handler. A key with "
            "<font name='Courier'>stt:stream</font> only must not be able to "
            "hit <font name='Courier'>/v1/usage/reset</font>.",
        ],
        "3 days",
    ))

    s.append(step(
        4, "Per-tenant audit log",
        [
            "Tables: <font name='Courier'>audit_log(tenant_id, actor_id, "
            "event_type, resource, created_at, trace_id, payload_jsonb)</font>.",
            "Events: key issued/revoked, session started/closed, transcript "
            "exported, usage reset, admin login, settings changed.",
            "Per-tenant export endpoint: "
            "<font name='Courier'>GET /v1/admin/audit?tenant_id=...</font>.",
        ],
        "1 week",
    ))

    s.append(step(
        5, "Multi-AZ deployment",
        [
            "Spread gateway pods across at least 2 availability zones. Pin "
            "Triton replicas to separate node groups in different AZs.",
            "Postgres: managed multi-AZ with automated failover. RPO 5 "
            "minutes via PITR. Document the RTO and chaos-test it twice a "
            "year.",
        ],
        "1 week",
    ))

    s.append(step(
        6, "Public status page",
        [
            "Statuspage.io, Better Stack, or Atlassian Statuspage. One "
            "component per region per service.",
            "Document SEV taxonomy and postmortem template. Wire alerts "
            "from your observability stack into an on-call rotation "
            "(PagerDuty, Opsgenie).",
        ],
        "2 days",
    ))

    s.append(step(
        7, "Begin SOC 2 Type II evidence collection",
        [
            "Pick an evidence-collection platform (Vanta, Drata, Secureframe). "
            "Connect your cloud accounts, code repo, ticketing, and HRIS.",
            "SOC 2 Type II is typically 9–12 months to first audit if you're "
            "starting from scratch. Start now; finish in Phase 4.",
        ],
        "ongoing",
    ))

    s.append(PageBreak())

    # -------- Phase 4 --------
    s.append(Paragraph("Phase 4 · Differentiation", h1_style))
    s.append(Paragraph("Months 6–12 · ~2–4 engineers, ML focus", muted_style))

    s.append(Paragraph(
        "Everything above gets you to parity with the field. Phase 4 is "
        "where you build the moat — fine-tuned per-tenant models, speaker "
        "identification across sessions, low-latency regional deployments.",
        body_style,
    ))

    s.append(step(
        1, "NeMo fine-tuning recipes (self-hosted only)",
        [
            "Package NVIDIA NeMo's "
            "<font name='Courier'>fine_tune_speech_recognition</font> recipe "
            "as a tenant-facing flow: upload labeled audio, train a Parakeet "
            "adapter, deploy automatically.",
            "Charge for fine-tuning as a separate SKU. This is the feature "
            "that wins regulated-industry deals.",
        ],
        "3–6 weeks",
    ))

    s.append(step(
        2, "Domain models",
        [
            "Pre-train models on medical, legal, finance, and contact-center "
            "corpora. Surface them as named models in "
            "<font name='Courier'>GET /v1/models</font>.",
            "Per-tenant default model selection. Each domain typically buys "
            "2–6 WER absolute on in-domain audio.",
        ],
        "4–8 weeks",
    ))

    s.append(step(
        3, "Speaker enrollment (cross-session identity)",
        [
            "pyannoteAI offers identification; Sortformer alone doesn't. "
            "Build the enrollment flow on top: tenant uploads a labeled "
            "voice sample, you store an embedding, future sessions resolve "
            "<font name='Courier'>spk_*</font> to real names.",
            "Privacy: voice embeddings are biometric data. Encrypt at rest "
            "with CMK; offer a delete-my-voiceprint API.",
        ],
        "4 weeks",
    ))

    s.append(step(
        4, "Co-located GPU regions",
        [
            "For latency-sensitive customers, deploy Triton pools in the "
            "same region as the customer's app servers. Saves 30–100 ms vs "
            "a cross-region path.",
            "Use Anycast or geo-aware DNS for ingress so the WebSocket lands "
            "in the closest region automatically.",
        ],
        "4–6 weeks",
    ))

    s.append(PageBreak())

    # -------- Appendix A --------
    s.append(Paragraph("Appendix A · Build-vs-buy decision matrix", h1_style))

    s.append(info_table(
        rows=[
            ["Capability",
             "Cloud-first wins by",
             "Self-hosted wins by"],
            ["Raw latency",
             "Sub-300 ms today, no GPU ops",
             "On-prem residency, no per-minute fee"],
            ["Managed scaling",
             "Thousands of streams out of the box",
             "Predictable cost at high utilization"],
            ["Diarization",
             "pyannoteAI Precision-2 quality",
             "On-prem, fine-tunable, no third-party data"],
            ["Reliability",
             "SOC 2 / HIPAA inherited",
             "Full control of incident response"],
            ["Accuracy tuning",
             "Keyterm Prompting (no retrain)",
             "Full NeMo fine-tuning"],
            ["Time to ship",
             "6–10 weeks",
             "6–9 months"],
            ["Engineering team",
             "1–2 engineers",
             "3–5 engineers + ML platform"],
        ],
        col_widths=[1.7 * inch, 2.65 * inch, 2.65 * inch],
    ))

    s.append(Spacer(1, 0.25 * inch))
    s.append(Paragraph(
        "<b>If forced to pick one row above:</b> most teams should start "
        "with cloud-first and add a self-hosted lane only when a specific "
        "deal demands it. That is the shortest path to 'max each category' "
        "with the lowest engineering bet.",
        body_style,
    ))

    s.append(PageBreak())

    # -------- Appendix B --------
    s.append(Paragraph("Appendix B · Open questions to answer before shipping", h1_style))

    questions = [
        ("Who is the customer?",
         "Voice agents, meeting transcription, contact center, healthcare scribe, "
         "broadcast captioning. Latency budget and diarization quality differ "
         "dramatically."),
        ("What is the compliance ceiling within 18 months?",
         "SOC 2 Type II is the minimum bar. HIPAA BAA, ISO 27001, FedRAMP "
         "Moderate change the Phase 3 scope materially."),
        ("Which languages?",
         "English-only favors NVIDIA Parakeet for speed and Canary-Qwen for "
         "accuracy. Multilingual favors Whisper-large-v3 or AssemblyAI "
         "Universal-3."),
        ("What is the cloud egress budget?",
         "Deepgram Nova-3 is roughly $0.0043–0.0058 per audio minute. At 1,000 "
         "concurrent streams 8 hours/day that is $80–100k/month. Self-hosted "
         "GPU is a fixed cost regardless of utilization."),
        ("Can you reserve GPU capacity?",
         "Self-hosted requires sustained access to H100/H200/A100. If you "
         "cannot reserve capacity ahead of time, cloud is the lower-risk bet "
         "until your spend justifies a commitment."),
    ]
    for q, a in questions:
        s.append(Paragraph(f"<b>{q}</b>", h3_style))
        s.append(Paragraph(a, body_style))

    s.append(PageBreak())

    # -------- Appendix C --------
    s.append(Paragraph("Appendix C · Sources (May 2026)", h1_style))
    s.append(Paragraph(
        "Latency benchmarks, leaderboards, and provider feature pages used "
        "in this guide. Validate before final architecture commits — the "
        "STT field moves quickly.",
        muted_style,
    ))

    sources = [
        ("Best Speech-to-Text APIs in 2026 — Deepgram",
         "deepgram.com/learn/best-speech-to-text-apis-2026"),
        ("Deepgram vs Speechmatics vs AssemblyAI — 2026 Guide",
         "deepgram.com/learn/deepgram-vs-speechmatics-vs-assemblyai"),
        ("Best Speech-to-Text Providers in 2026 — Coval benchmarks",
         "coval.ai/blog/best-speech-to-text-providers-in-2026"),
        ("Open ASR Leaderboard — Hugging Face",
         "huggingface.co/spaces/hf-audio/open_asr_leaderboard"),
        ("Open ASR Leaderboard — Trends and Insights",
         "huggingface.co/blog/open-asr-leaderboard"),
        ("NVIDIA Riva ASR Overview",
         "docs.nvidia.com/deeplearning/riva/user-guide/docs/asr"),
        ("NVIDIA Streaming Sortformer launch (blog)",
         "developer.nvidia.com/blog/identify-speakers-in-real-time-sortformer"),
        ("nvidia/diar_streaming_sortformer_4spk-v2 — Hugging Face",
         "huggingface.co/nvidia/diar_streaming_sortformer_4spk-v2"),
        ("pyannoteAI — Real-time diarization platform",
         "pyannote.ai"),
        ("pyannoteAI Precision-2 release",
         "pyannote.ai/blog/precision-2"),
        ("Deepgram Nova-3 launch",
         "deepgram.com/learn/introducing-nova-3-speech-to-text-api"),
        ("Deepgram Keyterm Prompting docs",
         "developers.deepgram.com/docs/keyterm"),
        ("Best open-source STT in 2026 — Northflank",
         "northflank.com/blog/best-open-source-speech-to-text-stt-model-in-2026-benchmarks"),
    ]
    for title, url in sources:
        s.append(Paragraph(
            f"&bull;&nbsp;&nbsp;{title} — <font color='#2563eb' name='Courier'>"
            f"{url}</font>",
            body_style,
        ))

    return s


def main():
    """
    Main function to generate the PDF guide.
    
    Creates the PDF document using ReportLab, builds the story content,
    and writes the output to the configured path.
    """
    logger.info(f"Starting PDF generation to {OUT_PATH}")
    
    doc = SimpleDocTemplate(
        str(OUT_PATH),
        pagesize=LETTER,
        leftMargin=0.85 * inch,
        rightMargin=0.85 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title="Streaming STT Platform — Step-by-Step Guide",
        author="true-streaming-stt-provider",
    )
    
    logger.info("Building PDF document")
    doc.build(build_story(), onFirstPage=page_chrome, onLaterPages=page_chrome)
    
    logger.info(f"Successfully wrote PDF to {OUT_PATH}")
    print(f"Wrote {OUT_PATH}")


if __name__ == "__main__":
    main()
