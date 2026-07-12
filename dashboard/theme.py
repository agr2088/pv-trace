"""Signal Station design tokens, global CSS, and component builders.

All visual constants, font injection, and HTML/SVG builder functions for the
PV-Trace dashboard live here. Pipeline code never imports from this module.
"""

import numpy as np
import plotly.graph_objects as go

# ---------------------------------------------------------------------------
# Color tokens — §1 of blueprint
# ---------------------------------------------------------------------------

DEEP_RADAR = "#0B1210"
CONSOLE_PANEL = "#14231F"
PHOSPHOR = "#4CFFA0"
AMBER_TRACE = "#FFB74D"
ALERT_CRIMSON = "#FF4757"
STATIC_FOG = "#7A8C86"

# Derived
PANEL_BORDER = "#1E332C"
PANEL_HOVER = "#1A2E28"
GRID_LINE = "#1E332C"

# Signal-ladder mapping (used by radar blips, badges, gauges)
SIGNAL_COLOR = {
    "signal": PHOSPHOR,
    "borderline": AMBER_TRACE,
    "noise": STATIC_FOG,
}

# ---------------------------------------------------------------------------
# Typography — §1 of blueprint
# ---------------------------------------------------------------------------

FONT_DISPLAY = "Space Grotesk"
FONT_BODY = "IBM Plex Sans"
FONT_MONO = "JetBrains Mono"

GOOGLE_FONTS_URL = (
    "https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700"
    "&family=IBM+Plex+Sans:wght@400;500"
    "&family=JetBrains+Mono:wght@400;500;600&display=swap"
)

# ---------------------------------------------------------------------------
# Global CSS — §9 of blueprint (console, not document)
# ---------------------------------------------------------------------------

GLOBAL_CSS = f"""
<style>
@import url('{GOOGLE_FONTS_URL}');

/* ── Reset ── */
html, body, [class*="css"] {{
    font-family: '{FONT_BODY}', sans-serif;
    color: #e5e7eb;
}}

/* ── Page background + scanline texture ── */
.stApp, .main .block-container {{
    background: {DEEP_RADAR} !important;
}}
.stApp::before {{
    content: '';
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: repeating-linear-gradient(
        0deg,
        transparent,
        transparent 2px,
        rgba(76, 255, 160, 0.015) 2px,
        rgba(76, 255, 160, 0.015) 4px
    );
    pointer-events: none;
    z-index: 0;
}}

/* ── Block container ── */
.block-container {{
    padding-top: 1rem !important;
    max-width: 1400px !important;
}}

/* ── Panel / card ── */
.station-panel {{
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 8px;
    padding: 1.25rem;
    min-height: 80px;
    transition: border-color 0.2s;
}}
.station-panel:hover {{
    border-color: {PHOSPHOR}40;
}}

/* ── Metric cards ── */
.metric-card {{
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-left: 3px solid {PHOSPHOR};
    border-radius: 8px;
    padding: 0.9rem 1rem;
}}
.metric-card-value {{
    font-family: '{FONT_MONO}', monospace;
    font-size: 1.5rem;
    font-weight: 600;
    color: {PHOSPHOR};
}}
.metric-card-label {{
    font-size: 0.75rem;
    color: {STATIC_FOG};
    text-transform: uppercase;
    letter-spacing: 0.05em;
}}

/* ── Threshold bar ── */
.threshold-bar {{
    position: relative;
    height: 6px;
    background: {PANEL_BORDER};
    border-radius: 3px;
    margin-top: 8px;
    overflow: visible;
}}
.threshold-fill {{
    height: 100%;
    border-radius: 3px;
    transition: width 0.6s ease;
}}
.threshold-marker {{
    position: absolute;
    top: -3px;
    width: 2px;
    height: 12px;
    background: {AMBER_TRACE};
    border-radius: 1px;
}}

/* ── Streamlit metric override ── */
div[data-testid="stMetric"] {{
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-left: 3px solid {PHOSPHOR};
    border-radius: 8px;
    padding: 0.9rem 1rem;
}}
div[data-testid="stMetricValue"] {{
    font-family: '{FONT_MONO}', monospace !important;
    color: {PHOSPHOR} !important;
}}
div[data-testid="stMetricLabel"] {{
    color: {STATIC_FOG} !important;
    font-size: 0.78rem;
}}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {{
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 8px;
    padding: 4px;
    gap: 2px;
}}
.stTabs [data-baseweb="tab"] {{
    border-radius: 6px;
    color: {STATIC_FOG};
    font-family: '{FONT_DISPLAY}', sans-serif;
    font-size: 0.85rem;
    font-weight: 500;
    padding: 6px 14px;
}}
.stTabs [aria-selected="true"] {{
    background: {PHOSPHOR} !important;
    color: {DEEP_RADAR} !important;
    font-weight: 700;
}}

/* ── Buttons ── */
.stButton > button {{
    border-radius: 6px;
    border: 1px solid {PANEL_BORDER};
    background: transparent;
    color: #e5e7eb;
    font-family: '{FONT_DISPLAY}', sans-serif;
    transition: all 0.15s;
}}
.stButton > button:hover {{
    border-color: {PHOSPHOR};
    color: {PHOSPHOR};
}}
.stButton > button[kind="primary"] {{
    background: {PHOSPHOR};
    color: {DEEP_RADAR};
    border: 0;
    font-weight: 600;
}}
.stButton > button[kind="primary"]:hover {{
    background: #5EFFAA;
    color: {DEEP_RADAR};
}}

/* ── Inputs ── */
.stTextInput input, .stTextArea textarea {{
    background: {DEEP_RADAR} !important;
    border: 1px solid {PANEL_BORDER} !important;
    color: #e5e7eb !important;
    border-radius: 6px;
}}
.stTextInput input:focus, .stTextArea textarea:focus {{
    border-color: {PHOSPHOR} !important;
    box-shadow: 0 0 0 2px rgba(76, 255, 160, 0.12) !important;
}}

/* ── Code blocks ── */
.stCode, code {{
    background: {DEEP_RADAR} !important;
    border: 1px solid {PANEL_BORDER} !important;
    border-radius: 6px;
    font-family: '{FONT_MONO}', monospace;
}}

/* ── DataFrames ── */
.stDataFrame {{ border-radius: 8px; overflow: hidden; }}

/* ── Progress ── */
.stProgress > div > div {{
    background: {PHOSPHOR};
}}

/* ── Expanders ── */
.streamlit-expanderHeader {{
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 8px;
    font-family: '{FONT_DISPLAY}', sans-serif;
}}

/* ── Dividers ── */
hr {{ border-color: {PANEL_BORDER}; }}

/* ── Scrollbar ── */
::-webkit-scrollbar {{ width: 6px; height: 6px; }}
::-webkit-scrollbar-track {{ background: {DEEP_RADAR}; }}
::-webkit-scrollbar-thumb {{ background: {PANEL_BORDER}; border-radius: 3px; }}
::-webkit-scrollbar-thumb:hover {{ background: {STATIC_FOG}; }}

/* ── Prefers reduced motion ── */
@media (prefers-reduced-motion: reduce) {{
    .radar-sweep {{ animation: none !important; }}
    .blink-cursor {{ animation: none !important; opacity: 1; }}
    .status-led-blink {{ animation: none !important; }}
}}

/* ── Header LED strip ── */
.led-strip {{
    display: flex;
    gap: 8px;
    align-items: center;
}}
.led {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    border: 1px solid {PANEL_BORDER};
}}
.led-active {{
    background: {PHOSPHOR};
    box-shadow: 0 0 6px {PHOSPHOR}80;
}}
.led-dim {{
    background: {STATIC_FOG}40;
}}
.led-blink {{
    background: {ALERT_CRIMSON};
    box-shadow: 0 0 6px {ALERT_CRIMSON}80;
    animation: led-blink 1s ease-in-out infinite;
}}

/* ── Station labels ── */
.station-label {{
    font-family: '{FONT_DISPLAY}', sans-serif;
    font-weight: 600;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    color: {STATIC_FOG};
}}

/* ── Status badge ── */
.status-badge {{
    display: inline-block;
    border-radius: 999px;
    padding: 0.15rem 0.6rem;
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.75rem;
    font-weight: 500;
}}
.badge-signal {{
    background: rgba(76, 255, 160, 0.12);
    color: {PHOSPHOR};
    border: 1px solid rgba(76, 255, 160, 0.3);
}}
.badge-borderline {{
    background: rgba(255, 183, 77, 0.12);
    color: {AMBER_TRACE};
    border: 1px solid rgba(255, 183, 77, 0.3);
}}
.badge-noise {{
    background: rgba(122, 140, 134, 0.12);
    color: {STATIC_FOG};
    border: 1px solid rgba(122, 140, 134, 0.3);
}}

/* ── Console transcript ── */
.transcript-frame {{
    background: {DEEP_RADAR};
    border: 1px solid {PANEL_BORDER};
    border-radius: 6px;
    padding: 1.2rem;
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.85rem;
    line-height: 1.6;
    color: {PHOSPHOR}CC;
    white-space: pre-wrap;
}}
.transcript-header {{
    display: flex;
    gap: 1rem;
    padding: 0.5rem 1rem;
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-bottom: none;
    border-radius: 6px 6px 0 0;
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.75rem;
    color: {STATIC_FOG};
}}
.blink-cursor {{
    display: inline-block;
    width: 8px;
    height: 1.1em;
    background: {PHOSPHOR};
    vertical-align: text-bottom;
    animation: blink 1s step-end infinite;
}}

/* ── Flight recorder tape ── */
.tape-strip {{
    display: flex;
    gap: 0;
    overflow-x: auto;
    padding: 1rem 0;
}}
.tape-tile {{
    flex-shrink: 0;
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 4px;
    padding: 0.5rem 0.7rem;
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.7rem;
    color: {STATIC_FOG};
    min-width: 120px;
}}
.tape-tile-break {{
    border-color: {ALERT_CRIMSON};
    position: relative;
}}
.tape-gap {{
    flex-shrink: 0;
    width: 16px;
    display: flex;
    align-items: center;
    justify-content: center;
    color: {ALERT_CRIMSON};
    font-weight: 700;
}}

/* ── Packet diagram ── */
.packet-diagram {{
    display: flex;
    gap: 0;
    margin: 0.5rem 0;
}}
.packet-segment {{
    flex: 1;
    text-align: center;
    padding: 0.6rem 0.4rem;
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.75rem;
    color: {STATIC_FOG};
    cursor: pointer;
    transition: all 0.15s;
}}
.packet-segment:first-child {{
    border-radius: 6px 0 0 6px;
}}
.packet-segment:last-child {{
    border-radius: 0 6px 6px 0;
}}
.packet-segment-active {{
    background: {PHOSPHOR}15;
    border-color: {PHOSPHOR}60;
    color: {PHOSPHOR};
}}

/* ── Decode strip ── */
.decode-strip {{
    display: flex;
    gap: 1.5rem;
    align-items: stretch;
}}
.decode-raw {{
    flex: 1;
    background: {DEEP_RADAR};
    border: 1px solid {PANEL_BORDER};
    border-radius: 6px;
    padding: 1rem;
    font-family: '{FONT_MONO}', monospace;
    font-size: 0.85rem;
}}
.decode-label {{
    font-family: '{FONT_DISPLAY}', sans-serif;
    font-weight: 600;
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: {STATIC_FOG};
    margin-bottom: 0.5rem;
}}
.decode-line {{
    flex: 0 0 40px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.decode-line-svg {{
    width: 40px;
    height: 2px;
}}
.decode-explained {{
    flex: 1;
    background: {CONSOLE_PANEL};
    border: 1px solid {PANEL_BORDER};
    border-radius: 6px;
    padding: 1rem;
    font-family: '{FONT_BODY}', sans-serif;
    font-size: 0.9rem;
}}

/* ── Keyframes ── */
@keyframes sweep {{
    from {{ transform: rotate(0deg); }}
    to {{ transform: rotate(360deg); }}
}}
@keyframes blink {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0; }}
}}
@keyframes led-blink {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.3; }}
}}
@keyframes draw-line {{
    from {{ stroke-dashoffset: 100; }}
    to {{ stroke-dashoffset: 0; }}
}}
@keyframes pulse-signal {{
    0%, 100% {{ opacity: 0.8; }}
    50% {{ opacity: 1; filter: brightness(1.5); }}
}}
</style>
"""


# ---------------------------------------------------------------------------
# Component builders
# ---------------------------------------------------------------------------

def inject_theme():
    """Return the global CSS injection string for st.markdown."""
    return GLOBAL_CSS


def header_led_strip(station_names: list[str], active: list[bool]) -> str:
    """Render 7 LED indicators, one per station. active[i] controls lit/dim."""
    dots = []
    for name, is_active in zip(station_names, active):
        css_class = "led led-active" if is_active else "led led-dim"
        dots.append(f'<span class="{css_class}" title="{name}"></span>')
    return (
        '<div class="led-strip">'
        + " ".join(dots)
        + f'<span style="font-family:\'{FONT_MONO}\',monospace;font-size:0.7rem;'
        f'color:{STATIC_FOG};margin-left:4px">{" ".join(chr(9679) * len(station_names))}</span>'
        + "</div>"
    )


def header_bar(active_stations: list[bool]) -> str:
    """Full header bar: LED strip + title. Drug input is a Streamlit column, not HTML."""
    station_names = [
        "Signal", "Clinical", "Narrative", "Deadline", "E2B", "NER", "Audit"
    ]
    leds = []
    for name, is_on in zip(station_names, active_stations):
        css = "led led-active" if is_on else "led led-dim"
        leds.append(f'<span class="{css}" title="{name}"></span>')
    led_html = '<div class="led-strip" style="display:flex;gap:6px;align-items:center;">'
    led_html += "".join(leds)
    led_html += "</div>"
    return f"""
    <div style="display:flex;align-items:center;gap:12px;padding:0.8rem 0 0.4rem 0;">
        {led_html}
        <span style="font-family:'{FONT_DISPLAY}',sans-serif;font-weight:700;font-size:1.3rem;
                      color:#e5e7eb;letter-spacing:0.04em;">
            PV-TRACE <span style="color:{STATIC_FOG};font-weight:400;font-size:0.85rem;">
            — SIGNAL STATION</span>
        </span>
    </div>
    """


def clinical_warning_banner() -> str:
    """Persistent clinical decision support warning — non-dismissible, §9."""
    return f"""
    <div style="background:{CONSOLE_PANEL};border:1px solid {PANEL_BORDER};
                border-left:3px solid {AMBER_TRACE};border-radius:6px;
                padding:0.5rem 0.8rem;margin-bottom:0.5rem;
                font-size:0.78rem;color:{STATIC_FOG};line-height:1.4;">
        <strong style="color:{AMBER_TRACE};">Clinical Decision Support Only</strong> —
        Outputs are generated from FAERS voluntary reports and are <em>not</em> a substitute
        for qualified pharmacovigilance physician review. All signals, narratives, and E2B
        exports require medical review before regulatory submission.
    </div>
    """


def status_led(is_valid: bool, blinking: bool = False) -> str:
    """Small circular LED for verification status."""
    if blinking:
        css = "led led-blink"
    elif is_valid:
        css = "led led-active"
    else:
        css = "led led-blink"
    return f'<span class="{css}" style="display:inline-block;vertical-align:middle;"></span>'


def metric_card(label: str, value: str, current: float, threshold: float,
                threshold_label: str = "") -> str:
    """Instrument card with value + horizontal threshold bar."""
    fill_pct = min((current / max(threshold, 0.01)) * 100, 100) if current > 0 else 0
    marker_pct = 100
    fill_color = PHOSPHOR if current >= threshold else STATIC_FOG
    return f"""
    <div class="metric-card">
        <div class="metric-card-label">{label}</div>
        <div class="metric-card-value">{value}</div>
        <div class="threshold-bar">
            <div class="threshold-fill" style="width:{fill_pct:.0f}%;background:{fill_color};"></div>
            <div class="threshold-marker" style="left:{marker_pct:.0f}%;"></div>
        </div>
        <div style="font-size:0.65rem;color:{STATIC_FOG};margin-top:3px;">
            {f"threshold: {threshold_label}" if threshold_label else ""}
        </div>
    </div>
    """


def noise_floor_ring_label(events_with_bg: int, events_excluded: int,
                           bg_failures: int) -> str:
    """P0-3 disclosure rendered as instrument caption (not a skimmable caption)."""
    parts = [f"<strong>{events_with_bg}</strong> top events: real FAERS background"]
    if events_excluded > 0:
        parts.append(f"<strong>{events_excluded}</strong> excluded (population-rate estimate)")
    if bg_failures > 0:
        parts.append(f"<strong>{bg_failures}</strong> failed (population-rate estimate)")
    return (
        f'<div style="font-family:\'{FONT_MONO}\',monospace;font-size:0.72rem;'
        f'color:{STATIC_FOG};padding:0.4rem 0;text-align:center;">'
        f'<span style="color:{AMBER_TRACE};">&#9678;</span> '
        + " &middot; ".join(parts)
        + "</div>"
    )


def sweep_overlay_html() -> str:
    """CSS-only rotating sweep line positioned over the radar chart.

    This is an absolutely-positioned conic-gradient wedge that rotates
    continuously. It MUST be wrapped in a container with position:relative
    that also contains the Plotly chart div.
    """
    return f"""
    <div class="radar-sweep" style="
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: 10;
        overflow: hidden;
        border-radius: 50%;
    ">
        <div style="
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: conic-gradient(
                from 0deg,
                transparent 0deg,
                transparent 350deg,
                {PHOSPHOR}18 355deg,
                {PHOSPHOR}30 358deg,
                {PHOSPHOR}18 360deg
            );
            animation: sweep 4s linear infinite;
        "></div>
    </div>
    """


def countdown_gauge(days_remaining: int, total_days: int, case_id: str) -> go.Figure:
    """Radial countdown gauge using Plotly go.Indicator.

    Arc fills from PHOSPHOR (plenty of time) through AMBER_TRACE (approaching)
    to ALERT_CRIMSON (overdue).
    """
    clamped = max(0, min(days_remaining, total_days))
    ratio = clamped / total_days if total_days > 0 else 0

    if days_remaining < 0:
        bar_color = ALERT_CRIMSON
    elif days_remaining <= 3:
        bar_color = ALERT_CRIMSON
    elif ratio <= 0.3:
        bar_color = AMBER_TRACE
    else:
        bar_color = PHOSPHOR

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=clamped,
        number={"font": {"family": FONT_MONO, "size": 28, "color": bar_color}},
        gauge={
            "axis": {"range": [0, total_days], "tickwidth": 0,
                     "tickcolor": STATIC_FOG, "tickfont": {"color": STATIC_FOG, "size": 9}},
            "bar": {"color": bar_color, "thickness": 0.3},
            "bgcolor": CONSOLE_PANEL,
            "borderwidth": 1,
            "bordercolor": PANEL_BORDER,
            "steps": [
                {"range": [0, total_days * 0.3], "color": "rgba(255,71,87,0.08)"},
                {"range": [total_days * 0.3, total_days * 0.7], "color": "rgba(255,183,77,0.06)"},
                {"range": [total_days * 0.7, total_days], "color": "rgba(76,255,160,0.03)"},
            ],
        },
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"family": FONT_MONO, "color": STATIC_FOG},
        height=160,
        margin=dict(t=30, b=10, l=20, r=20),
    )
    return fig


def packet_segment_html(label: str, is_active: bool) -> str:
    """Single segment in the E2B packet structure diagram."""
    css = "packet-segment packet-segment-active" if is_active else "packet-segment"
    return f'<div class="{css}">{label}</div>'


def flight_recorder_tile(entry: dict, is_break: bool = False) -> str:
    """Single tile in the flight-recorder audit tape."""
    css = "tape-tile tape-tile-break" if is_break else "tape-tile"
    step = entry.get("step", "?")
    status = entry.get("status", "?")
    ts = entry.get("timestamp", "")[:10]
    status_color = ALERT_CRIMSON if status in ("error", "failed") else PHOSPHOR
    return (
        f'<div class="{css}">'
        f'<div style="color:{status_color};font-weight:500;">{step}</div>'
        f'<div>{status}</div>'
        f'<div style="color:{STATIC_FOG};font-size:0.65rem;">{ts}</div>'
        f'</div>'
    )


def decode_strip_html(raw_label: str, raw_text: str,
                      explained_text: str, is_template: bool = False) -> str:
    """Signal-to-plain-language decode strip for Station II."""
    template_note = ""
    if is_template:
        template_note = (
            f'<div style="font-size:0.72rem;color:{STATIC_FOG};'
            f'margin-top:0.3rem;font-style:italic;">'
            f'Template fallback — not model-generated</div>'
        )
    return f"""
    <div class="decode-strip">
        <div class="decode-raw">
            <div class="decode-label">Raw Signal</div>
            <div>{raw_text}</div>
        </div>
        <div class="decode-line">
            <svg class="decode-line-svg" viewBox="0 0 40 2">
                <line x1="0" y1="1" x2="40" y2="1" stroke="{STATIC_FOG}"
                      stroke-width="1" stroke-dasharray="4 3"
                      style="animation: draw-line 1s ease forwards;
                             stroke-dashoffset: 40;" />
            </svg>
        </div>
        <div class="decode-explained">
            <div class="decode-label">Decoded</div>
            <div>{explained_text}</div>
            {template_note}
        </div>
    </div>
    """


def transcript_frame(case_id: str, metadata: str, narrative: str) -> str:
    """Console-transcript frame for Station III narratives."""
    return f"""
    <div class="transcript-header">
        <span>Case {case_id}</span>
        <span>{metadata}</span>
    </div>
    <div class="transcript-frame">{narrative}<span class="blink-cursor"></span></div>
    """


def extraction_mode_badge(mode: str, model_name: str = "") -> str:
    """P1-7 extraction mode disclosure for Station VI."""
    if mode == "NER":
        bg = f"{PHOSPHOR}15"
        border = f"{PHOSPHOR}40"
        color = PHOSPHOR
        label = f"scispaCy ({model_name})" if model_name else "Biomedical NER"
    else:
        bg = f"{AMBER_TRACE}15"
        border = f"{AMBER_TRACE}40"
        color = AMBER_TRACE
        label = "Fallback: SOC-keyword matching only — no biomedical NER model loaded"
    return (
        f'<div style="display:inline-block;background:{bg};border:1px solid {border};'
        f'border-radius:999px;padding:0.2rem 0.7rem;font-family:\'{FONT_MONO}\',monospace;'
        f'font-size:0.75rem;color:{color};margin-top:0.5rem;">'
        f'{label}</div>'
    )


def expectedness_banner() -> str:
    """P1-6 expectedness caveat for Station IV — always visible at top."""
    return f"""
    <div style="background:{CONSOLE_PANEL};border:1px solid {PANEL_BORDER};
                border-left:3px solid {AMBER_TRACE};border-radius:6px;
                padding:0.6rem 0.9rem;margin-bottom:0.8rem;">
        <div style="font-family:'{FONT_DISPLAY}',sans-serif;font-weight:600;
                    font-size:0.8rem;color:{AMBER_TRACE};margin-bottom:0.2rem;">
            Expectedness Caveat (ICH E2A)
        </div>
        <div style="font-size:0.78rem;color:{STATIC_FOG};line-height:1.4;">
            All 7-day and 15-day deadlines assume the reported reaction is
            <strong>unexpected</strong> per ICH E2A. FAERS/openFDA does not contain
            product labeling data needed to verify listedness. Confirm expectedness
            against approved product labeling before regulatory submission.
        </div>
    </div>
    """


def reactionoutcome_disclosure() -> str:
    """P1-5 disclosure placed under E2B reaction segment."""
    return (
        f'<div style="font-family:\'{FONT_MONO}\',monospace;font-size:0.72rem;'
        f'color:{STATIC_FOG};padding:0.3rem 0;">'
        f'<span style="color:{AMBER_TRACE};">&#9678;</span> '
        f'Per-reaction recovery status from openFDA <code>reactionoutcome</code> field. '
        f'Where absent, defaults to "unknown" (code 6). Verify against source data.'
        f'</div>'
    )


def empty_station_shell(label: str = "No signal acquired") -> str:
    """Default empty state for any station before data is loaded."""
    return f"""
    <div class="station-panel" style="display:flex;align-items:center;
         justify-content:center;min-height:200px;opacity:0.5;">
        <div style="text-align:center;">
            <div style="font-family:'{FONT_DISPLAY}',sans-serif;font-size:1.2rem;
                        color:{STATIC_FOG};margin-bottom:0.3rem;">&#9678;</div>
            <div style="font-family:'{FONT_MONO}',sans-serif;font-size:0.8rem;
                        color:{STATIC_FOG};">{label}</div>
        </div>
    </div>
    """


def status_bar(text: str, color: str = STATIC_FOG) -> str:
    """Small status text line for fetch progress."""
    return (
        f'<div style="font-family:\'{FONT_MONO}\',monospace;font-size:0.75rem;'
        f'color:{color};padding:0.2rem 0;">{text}</div>'
    )
