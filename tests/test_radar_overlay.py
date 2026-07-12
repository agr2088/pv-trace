"""Minimal standalone test for radar sweep overlay positioning.

Run with: streamlit run tests/test_radar_overlay.py
Open in browser and visually confirm:
1. The Plotly polar chart renders centered
2. The sweep line (faint green rotating wedge) is positioned ON TOP of the chart
3. The sweep rotates smoothly
4. Red debug borders show the overlay container's actual bounds

If the sweep is offset, misaligned, or not visible, the DOM structure has changed
and the overlay approach needs to be reworked before building Station I.
"""
import sys
sys.path.insert(0, ".")

import streamlit as st
import plotly.graph_objects as go
import numpy as np

from dashboard.theme import (
    GLOBAL_CSS, DEEP_RADAR, CONSOLE_PANEL, PHOSPHOR, STATIC_FOG,
    GRID_LINE, FONT_MONO,
)

st.set_page_config(page_title="Radar Overlay Test", layout="wide")
st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

st.title("Radar Sweep Overlay Validation")
st.caption("If you can see a rotating green wedge over the polar chart, the overlay works.")

# --- Build sample data ---
np.random.seed(42)
n_events = 12
events = [f"Event-{i}" for i in range(n_events)]
prrs = np.random.uniform(1.5, 25, n_events)
cases = np.random.randint(5, 80, n_events)
angles = np.linspace(0, 360, n_events, endpoint=False)

fig = go.Figure()
for i, (ev, prr, a, theta) in enumerate(zip(events, prrs, cases, angles)):
    r = np.log10(max(prr, 1.01))
    color = PHOSPHOR if prr > 4 else STATIC_FOG
    fig.add_trace(go.Scatterpolar(
        r=[r], theta=[theta], mode="markers",
        marker=dict(size=8 + np.log1p(a) * 2, color=color,
                    line=dict(color=DEEP_RADAR, width=1)),
        name=ev,
        hovertemplate=f"{ev}<br>PRR={prr:.2f}<br>a={a}<extra></extra>",
    ))
fig.update_layout(
    polar=dict(
        bgcolor=CONSOLE_PANEL,
        radialaxis=dict(color=STATIC_FOG, gridcolor=GRID_LINE, range=[0, 1.6]),
        angularaxis=dict(showticklabels=False, gridcolor=GRID_LINE),
    ),
    paper_bgcolor="rgba(0,0,0,0)",
    font=dict(family=FONT_MONO, color=PHOSPHOR),
    showlegend=False,
    height=500,
    margin=dict(t=30, b=30, l=40, r=40),
)

# --- Method A: Wrapper div approach ---
st.subheader("Method A: Wrapper div with position:relative")
st.markdown("""
<div style="position:relative; width:100%; border:2px dashed #ff4757; min-height:500px;">
""", unsafe_allow_html=True)

# Render the chart first
chart_slot_a = st.empty()
chart_slot_a.plotly_chart(fig, use_container_width=True, key="radar_a")

# Overlay on top
st.markdown("""
    <div style="
        position: absolute;
        top: 0; left: 0; right: 0; bottom: 0;
        pointer-events: none;
        z-index: 10;
        overflow: hidden;
        border-radius: 50%;
        border: 2px solid #ff4757;
    ">
        <div style="
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: conic-gradient(
                from 0deg,
                transparent 0deg,
                transparent 350deg,
                #4CFFA018 355deg,
                #4CFFA030 358deg,
                #4CFFA018 360deg
            );
            animation: sweep 4s linear infinite;
        "></div>
    </div>
""", unsafe_allow_html=True)

st.markdown("</div>", unsafe_allow_html=True)

st.markdown("---")

# --- Method B: Using st.columns as container ---
st.subheader("Method B: Inside st.columns (Streamlit manages layout)")
col_chart, col_overlay = st.columns([5, 1])
with col_chart:
    chart_slot_b = st.empty()
    chart_slot_b.plotly_chart(fig, use_container_width=True, key="radar_b")
    # Overlay injected directly below the chart within same column
    st.markdown("""
    <div style="position:relative; margin-top:-500px; height:500px;
                pointer-events:none; z-index:10; overflow:hidden;
                border:2px dashed #FFB74D;">
        <div style="
            position: absolute;
            top: -50%; left: -50%;
            width: 200%; height: 200%;
            background: conic-gradient(
                from 0deg,
                transparent 0deg,
                transparent 350deg,
                #FFB74D18 355deg,
                #FFB74D30 358deg,
                #FFB74D18 360deg
            );
            animation: sweep 4s linear infinite;
        "></div>
    </div>
    """, unsafe_allow_html=True)

st.markdown("---")

# --- Method C: st.components.v1.html for precise control ---
st.subheader("Method C: Using st.empty + manual HTML injection")
st.markdown("""
<div id="radar-container-c" style="position:relative;width:100%;height:520px;
     border:2px dashed #4CFFA0;">
</div>
""", unsafe_allow_html=True)

st.info(
    "Method C uses a fixed-height container. The chart should render inside it "
    "via JavaScript. If Streamlit's DOM prevents this, Method A or B is the fallback."
)

st.markdown("---")

# --- Debug: DOM structure info ---
st.subheader("DOM Structure Check")
st.code("""
What to inspect in browser DevTools:
1. Find the Plotly chart div (class "stPlotlyChart" or "js-plotly-plot")
2. Check if the overlay div is a SIBLING or CHILD with position:absolute
3. Verify the overlay's bounding box overlaps the chart's bounding box
4. The red/orange/green dashed borders are debug aids — they show container bounds

If the overlay is BEHIND the chart (z-index issue), increase z-index.
If the overlay is OFFSET (wrong container), the position:relative parent is wrong.
If the animation is invisible, the conic-gradient may need different rgba values.
""", language="text")

st.markdown("---")
st.success(
    "If you can see the rotating sweep over the polar chart above, "
    "the overlay approach works. If not, report which method failed and how."
)
