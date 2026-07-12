"""PV-Trace Streamlit dashboard."""

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from audit.logger import AuditLogger
from config.settings import (
    APP_NAME,
    APP_PAGE_TITLE,
    APP_SUBTITLE,
    AUDIT_DISPLAY_LIMIT,
    AUDIT_LOG_PATH,
    BACKGROUND_EVENT_LIMIT,
    CACHE_TTL_SECONDS,
    CHI2_THRESHOLD,
    COLOR_BORDER,
    COLOR_CARD,
    COLOR_DANGER,
    COLOR_MUTED,
    COLOR_PRIMARY,
    COLOR_SIDEBAR,
    COLOR_TEXT,
    E2B_BATCH_LIMIT,
    EXAMPLE_DRUGS,
    MIN_CASE_COUNT,
    NARRATIVE_DISPLAY_LIMIT,
    PRR_THRESHOLD,
    ROR_THRESHOLD,
)
from pipeline.deadline_calculator import DeadlineCalculator
from pipeline.e2b_exporter import E2BExporter
from pipeline.explainer import ClinicalExplainer
from pipeline.ingestor import OpenFDAIngestor
from pipeline.narrative_writer import NarrativeWriter
from pipeline.ner_extractor import NERExtractor
from pipeline.signal_detector import SignalDetector
from utils.formatters import OutputFormatter
from utils.validators import InputValidator


st.set_page_config(
    page_title=APP_PAGE_TITLE,
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def inject_css():
    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,wght@0,300;0,400;0,500;0,700;1,400&family=DM+Mono:wght@400;500&display=swap');

        html, body, [class*="css"] {{
            font-family: 'DM Sans', sans-serif;
        }}

        section[data-testid="stSidebar"] {{
            background: {COLOR_SIDEBAR};
            border-right: 1px solid {COLOR_BORDER};
        }}

        .block-container {{ padding-top: 1.5rem; max-width: 1400px; }}

        .pv-card {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 10px;
            padding: 1.25rem;
            min-height: 100px;
            transition: border-color 0.2s;
        }}
        .pv-card:hover {{ border-color: {COLOR_PRIMARY}; }}

        div[data-testid="stMetric"] {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-left: 3px solid {COLOR_PRIMARY};
            border-radius: 10px;
            padding: 0.9rem 1rem;
        }}
        div[data-testid="stMetricValue"] {{
            font-family: 'DM Mono', monospace;
            color: {COLOR_TEXT} !important;
        }}
        div[data-testid="stMetricLabel"] {{
            color: {COLOR_MUTED} !important;
            font-size: 0.8rem;
        }}

        .badge {{
            display: inline-block;
            border-radius: 999px;
            padding: 0.2rem 0.7rem;
            font-family: 'DM Mono', monospace;
            font-size: 0.78rem;
            font-weight: 500;
            margin: 2px;
        }}
        .badge-signal {{ background: rgba(239,68,68,0.15); color: {COLOR_DANGER}; border: 1px solid rgba(239,68,68,0.3); }}
        .badge-monitor {{ background: rgba(0,212,170,0.12); color: {COLOR_PRIMARY}; border: 1px solid rgba(0,212,170,0.3); }}
        .badge-overdue {{ background: rgba(239,68,68,0.15); color: {COLOR_DANGER}; }}

        .stButton > button {{
            border-radius: 8px;
            border: 1px solid {COLOR_BORDER};
            background: transparent;
            color: {COLOR_TEXT};
            transition: all 0.15s;
        }}
        .stButton > button:hover {{
            border-color: {COLOR_PRIMARY};
            color: {COLOR_PRIMARY};
        }}
        .stButton > button[kind="primary"] {{
            background: {COLOR_PRIMARY};
            color: #0a0f1e;
            border: 0;
            font-weight: 600;
        }}
        .stButton > button[kind="primary"]:hover {{
            background: #00b899;
            color: #0a0f1e;
        }}

        .stTabs [data-baseweb="tab-list"] {{
            background: {COLOR_CARD};
            border-radius: 10px;
            padding: 4px;
            gap: 2px;
        }}
        .stTabs [data-baseweb="tab"] {{
            border-radius: 7px;
            color: {COLOR_MUTED};
            font-size: 0.88rem;
            font-weight: 500;
            padding: 6px 14px;
        }}
        .stTabs [aria-selected="true"] {{
            background: {COLOR_PRIMARY} !important;
            color: #0a0f1e !important;
            font-weight: 700;
        }}

        .stDataFrame {{ border-radius: 8px; overflow: hidden; }}
        hr {{ border-color: {COLOR_BORDER}; }}
        .stCode, code {{
            background: {COLOR_CARD} !important;
            border: 1px solid {COLOR_BORDER} !important;
            border-radius: 6px;
        }}

        .stTextInput input, .stTextArea textarea {{
            background: {COLOR_CARD} !important;
            border: 1px solid {COLOR_BORDER} !important;
            color: {COLOR_TEXT} !important;
            border-radius: 8px;
        }}
        .stTextInput input:focus, .stTextArea textarea:focus {{
            border-color: {COLOR_PRIMARY} !important;
            box-shadow: 0 0 0 2px rgba(0,212,170,0.15) !important;
        }}

        .stProgress > div > div {{
            background: {COLOR_PRIMARY};
        }}

        .streamlit-expanderHeader {{
            background: {COLOR_CARD};
            border: 1px solid {COLOR_BORDER};
            border-radius: 8px;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_fetch(drug_name: str):
    ingestor = OpenFDAIngestor()
    return ingestor.fetch_drug_events(drug_name), ingestor.fetch_total_count()


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def fetch_background_counts(event_pts_json: str) -> dict:
    import json as _json
    import logging

    event_pts = _json.loads(event_pts_json)
    ingestor = OpenFDAIngestor()
    counts = {}
    failures = 0
    for event_pt in event_pts:
        try:
            count = ingestor.fetch_event_total_count(event_pt)
            counts[event_pt] = count
        except Exception:
            failures += 1
            logging.warning("Background count unavailable for '%s'; using population-rate estimate", event_pt)
    return {"counts": counts, "failures": failures}


def run_pipeline(drug_name: str) -> dict:
    logger = AuditLogger(drug_name)
    status = st.status(f"Running PV-Trace analysis for {drug_name}", expanded=True)
    progress = st.progress(0, text="Starting analysis...")

    try:
        status.write("Connecting to openFDA FAERS and fetching adverse event reports...")
        logger.log_step("ingestion", "started", {"drug_name": drug_name})
        events_df, total_count = cached_fetch(drug_name)
        logger.log_step("ingestion", "completed", {"cases": len(events_df), "total_db_count": total_count})
        progress.progress(20, text=f"Fetched {len(events_df)} FAERS cases")

        status.write("Fetching real FAERS background event counts for top events...")
        filled = events_df["event_pt"].fillna("Unspecified adverse event")
        event_counts_s = events_df.assign(event_pt=filled).groupby("event_pt")["primaryid"].nunique()
        top_events = event_counts_s.sort_values(ascending=False).head(BACKGROUND_EVENT_LIMIT)
        total_distinct_events = len(event_counts_s)
        events_excluded = max(0, total_distinct_events - BACKGROUND_EVENT_LIMIT)
        import json as _json
        bg_result = fetch_background_counts(_json.dumps(list(top_events.index)))
        event_background_counts = bg_result["counts"]
        bg_failures = bg_result["failures"]
        status.write(
            f"Background counts fetched for {len(event_background_counts)} of {len(top_events)} top events"
            + (f"; {bg_failures} failed (population-rate estimate used)" if bg_failures else "")
            + (f"; {events_excluded} lower-frequency events excluded" if events_excluded else "")
        )
        progress.progress(30, text="Background counts fetched")

        status.write("Calculating PRR, ROR, EBGM, and chi-square signal statistics...")
        detector = SignalDetector()
        signals_df = detector.analyze_drug(events_df, total_count, event_background_counts=event_background_counts)
        logger.log_step("signal_detection", "completed", {"events_analyzed": len(signals_df)})
        for _, row in signals_df.head(AUDIT_DISPLAY_LIMIT).iterrows():
            logger.log_signal(drug_name, row["event_pt"], row["prr"], row["ror"], bool(row["is_signal"]))
        progress.progress(40, text=f"Analyzed {len(signals_df)} adverse event terms")

        status.write("Building clinical explanations for detected signals...")
        explainer = ClinicalExplainer()
        explained_df = explainer.explain_batch(signals_df, drug_name)
        logger.log_step("clinical_explanation", "completed", {"rows": len(explained_df)})
        progress.progress(55, text="Clinical signal explanations complete")

        status.write("Generating ICH E2D-style ICSR narratives...")
        writer = NarrativeWriter()
        narratives = writer.generate_batch(events_df)
        for item in narratives:
            digest = hashlib.sha256(item["narrative"].encode("utf-8")).hexdigest()
            logger.log_narrative(str(item["case_id"]), digest)
        progress.progress(70, text=f"Generated {len(narratives)} narratives")

        status.write("Assigning ICH E2A 7/15/90-day reporting deadlines...")
        calculator = DeadlineCalculator()
        deadlines_df = calculator.calculate_batch(events_df)
        logger.log_step("deadline_calculation", "completed", {"rows": len(deadlines_df)})
        progress.progress(85, text="Deadline calculation complete")

        status.write("Preparing ICH E2B(R3)-style XML exports and audit summary...")
        cases_for_xml = []
        narrative_lookup = {str(item["case_id"]): item["narrative"] for item in narratives}
        for _, row in events_df.head(E2B_BATCH_LIMIT).iterrows():
            case = row.to_dict()
            case["narrative"] = narrative_lookup.get(str(case.get("primaryid", "")), "")
            cases_for_xml.append(case)
        e2b_exports = E2BExporter().export_batch(cases_for_xml)
        logger.log_step("e2b_export", "completed", {"exports": len(e2b_exports)})
        progress.progress(100, text="Analysis complete")

        summary = logger.get_run_summary()
        status.update(label=f"PV-Trace analysis complete for {drug_name}", state="complete", expanded=False)
        return {
            "events_df": events_df,
            "signals_df": explained_df,
            "narratives": narratives,
            "deadlines_df": deadlines_df,
            "e2b_exports": e2b_exports,
            "run_summary": summary,
            "bg_metadata": {
                "total_distinct_events": total_distinct_events,
                "events_with_background": len(event_background_counts),
                "events_excluded": events_excluded,
                "bg_failures": bg_failures,
            },
        }
    except Exception:
        status.update(label=f"PV-Trace analysis failed for {drug_name}", state="error", expanded=True)
        raise


def load_audit_entries() -> pd.DataFrame:
    path = Path(AUDIT_LOG_PATH)
    if not path.exists():
        return pd.DataFrame(columns=["timestamp", "step", "status", "details"])
    lines = path.read_text(encoding="utf-8").splitlines()[-AUDIT_DISPLAY_LIMIT:]
    entries = [json.loads(line) for line in lines if line.strip()]
    return pd.DataFrame(entries)


def make_narrative_zip(narratives: list[dict]) -> bytes:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        narrative_dir = temp_path / "narratives"
        narrative_dir.mkdir()
        for item in narratives:
            case_id = item.get("case_id") or "unknown"
            file_path = narrative_dir / f"case_{case_id}.txt"
            file_path.write_text(item["narrative"], encoding="utf-8")
        archive_path = shutil.make_archive(str(temp_path / "icsr_narratives"), "zip", narrative_dir)
        zip_bytes = Path(archive_path).read_bytes()
        return zip_bytes


def render_landing():
    def trigger_analysis(selected_drug):
        st.session_state.drug_input = selected_drug
        st.session_state.run_requested = True

    st.markdown(
        f"""
        <div style='text-align:center;padding:2rem 0 1rem'>
            <div style='font-family:DM Mono,monospace;font-size:0.8rem;color:{COLOR_PRIMARY};
                        letter-spacing:0.2em;text-transform:uppercase;margin-bottom:0.5rem'>
                Pharmacovigilance Signal Intelligence
            </div>
            <h1 style='font-size:2.4rem;font-weight:700;margin:0;letter-spacing:0'>
                PV-Trace
            </h1>
            <p style='color:{COLOR_MUTED};margin-top:0.5rem;font-size:1rem'>
                Real-time FAERS signal detection | WHO-UMC criteria | ICH E2A deadlines | spaCy NER
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(4)
    cards = [
        ("Live FAERS Data", "Pull up to 500 real adverse event reports from openFDA in real time."),
        ("Signal Detection", "PRR, ROR, EBGM, Chi2 with WHO-UMC / Evans criteria flagging."),
        ("ICH E2A Deadlines", "7 / 15 / 90-day regulatory reporting timelines per case."),
        ("NER Extractor", "spaCy NLP to extract drug names and AE terms from clinical free text."),
    ]
    for col, (title, body) in zip(cols, cards):
        col.markdown(
            f"<div class='pv-card'><strong>{title}</strong>"
            f"<p style='color:{COLOR_MUTED};font-size:0.85rem;margin-top:0.4rem'>{body}</p></div>",
            unsafe_allow_html=True,
        )

    st.write("")
    st.caption("Quick examples")
    example_cols = st.columns(len(EXAMPLE_DRUGS))
    for col, drug in zip(example_cols, EXAMPLE_DRUGS):
        col.button(drug, use_container_width=True, on_click=trigger_analysis, args=(drug,))

    st.write("")
    st.markdown(
        f"<p style='text-align:center;color:{COLOR_MUTED};font-size:0.78rem'>"
        "Built by <strong>Aruri Gowtham</strong> | Pharm.D + PvPI ADR Experience | Data Science 9.0 CGPA"
        "</p>",
        unsafe_allow_html=True,
    )


def render_signal_tab(results: dict, formatter: OutputFormatter, drug_name: str):
    events_df = results["events_df"]
    signals_df = results["signals_df"]
    st.subheader(f"Signal Analysis: {drug_name}")
    col1, col2, col3, col4 = st.columns(4)
    signal_count = int(signals_df["is_signal"].sum()) if not signals_df.empty else 0
    highest_prr = signals_df["prr"].max() if not signals_df.empty else 0
    most_reported = signals_df.iloc[0]["event_pt"] if not signals_df.empty else "N/A"
    col1.metric("Total unique cases", events_df["primaryid"].nunique() if not events_df.empty else 0)
    col2.metric("Signals detected", signal_count)
    col3.metric("Highest PRR", f"{highest_prr:.2f}" if pd.notna(highest_prr) else "N/A")
    col4.metric("Most reported event", most_reported)

    bg = results.get("bg_metadata")
    if bg:
        parts = [
            f"Real FAERS background counts used for **{bg['events_with_background']}** top events by case count."
        ]
        if bg["events_excluded"] > 0:
            parts.append(
                f"**{bg['events_excluded']}** lower-frequency events excluded from signal scoring "
                f"(population-rate estimate applied instead)."
            )
        if bg["bg_failures"] > 0:
            parts.append(
                f"**{bg['bg_failures']}** event(s) failed during background fetch "
                f"(population-rate estimate used for those events)."
            )
        st.caption(" ".join(parts))

    display_df = signals_df.copy()
    if not display_df.empty:
        display_df["Event"] = display_df["event_pt"]
        display_df["Cases"] = display_df["case_count"]
        display_df["PRR"] = display_df.apply(
            lambda row: formatter.format_prr(row["prr"], row["prr_lower"], row["prr_upper"]), axis=1
        )
        display_df["ROR"] = display_df.apply(
            lambda row: formatter.format_prr(row["ror"], row["ror_lower"], row["ror_upper"]), axis=1
        )
        display_df["EBGM"] = display_df["ebgm"].map(lambda value: f"{value:.2f}" if pd.notna(value) else "N/A")
        display_df["Chi2"] = display_df["chi2"].map(lambda value: f"{value:.2f}")
        display_df["Signal"] = display_df["is_signal"].map(formatter.format_signal_badge)
    table = formatter.dataframe_to_display(display_df, ["Event", "Cases", "PRR", "ROR", "EBGM", "Chi2", "Signal"])
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cases": st.column_config.NumberColumn("Cases", format="%d 📄"),
            "PRR": st.column_config.TextColumn("PRR (95% CI)", width="medium"),
            "ROR": st.column_config.TextColumn("ROR (95% CI)", width="medium"),
            "Signal": st.column_config.TextColumn("Signal Status"),
        },
    )
    if signals_df.empty:
        st.info(
            "No adverse event terms were found in the FAERS data for this drug. "
            "This may indicate low report volume, a brand name vs. generic mismatch, "
            "or that the drug has very few spontaneous reports. Try the generic INN name."
        )
    elif signal_count == 0:
        st.success(
            f"No signals meeting WHO-UMC criteria (PRR >= {PRR_THRESHOLD}, Chi2 >= {CHI2_THRESHOLD}, "
            f"n >= {MIN_CASE_COUNT}) were detected for this drug across {len(signals_df)} adverse event terms. "
            "Continue routine pharmacovigilance monitoring per standard practice."
        )
    st.download_button(
        "Download signal CSV",
        signals_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{drug_name.lower()}_signals.csv",
        mime="text/csv",
    )

    if not signals_df.empty:
        st.divider()
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            top_n = signals_df.head(15).copy()
            fig_prr = px.bar(
                top_n,
                x="prr",
                y="event_pt",
                orientation="h",
                color="is_signal",
                color_discrete_map={True: "#ef4444", False: "#00d4aa"},
                labels={"prr": "PRR", "event_pt": "Adverse Event", "is_signal": "Signal"},
                title="PRR by Adverse Event (Top 15)",
            )
            fig_prr.add_vline(x=PRR_THRESHOLD, line_dash="dash", line_color="#e2b86a", annotation_text="WHO-UMC threshold")
            fig_prr.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                height=400,
                showlegend=True,
            )
            st.plotly_chart(fig_prr, use_container_width=True)

        with chart_col2:
            scatter_df = signals_df.dropna(subset=["prr", "ror"]).head(30)
            fig_scatter = px.scatter(
                scatter_df,
                x="prr",
                y="ror",
                size="case_count",
                color="is_signal",
                color_discrete_map={True: "#ef4444", False: "#00d4aa"},
                hover_name="event_pt",
                labels={"prr": "PRR", "ror": "ROR", "is_signal": "Signal"},
                title="PRR vs ROR Disproportionality Plot",
            )
            fig_scatter.add_vline(x=PRR_THRESHOLD, line_dash="dash", line_color="#e2b86a")
            fig_scatter.add_hline(y=ROR_THRESHOLD, line_dash="dash", line_color="#e2b86a")
            fig_scatter.update_layout(
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font_color="#e5e7eb",
                height=400,
            )
            fig_scatter.update_traces(
                marker=dict(line=dict(width=1, color="#1f2937")),
                hovertemplate="<b>%{hovertext}</b><br><br>PRR Score: %{x:.2f}<br>ROR Score: %{y:.2f}<br>Case Count: %{marker.size}<extra></extra>",
            )
            st.plotly_chart(fig_scatter, use_container_width=True)


def render_clinical_tab(results: dict):
    signals = results["signals_df"]
    detected = signals[signals["is_signal"].astype(bool)] if not signals.empty else pd.DataFrame()
    if detected.empty:
        st.info("No signals meeting WHO-UMC criteria detected")
        return
    for _, row in detected.iterrows():
        st.markdown(
            f"<div class='pv-card'><h3>{row['event_pt']}</h3>"
            f"<span class='badge badge-signal'>PRR {row['prr']:.2f}</span><p>{row['explanation']}</p></div>",
            unsafe_allow_html=True,
        )
        with st.expander("Full stats"):
            st.json(row[["case_count", "prr", "ror", "ebgm", "chi2", "is_signal"]].to_dict())


def render_narrative_tab(results: dict):
    writer = NarrativeWriter()
    all_narratives = results["narratives"]
    serious_narratives = [n for n in all_narratives if n.get("serious")]
    non_serious = [n for n in all_narratives if not n.get("serious")]
    narratives = (serious_narratives + non_serious)[:NARRATIVE_DISPLAY_LIMIT]

    col_a, col_b = st.columns(2)
    col_a.metric("Total narratives generated", len(all_narratives))
    col_b.metric("Serious cases (priority review)", len(serious_narratives))
    if len(all_narratives) > NARRATIVE_DISPLAY_LIMIT:
        st.caption(
            f"Showing {NARRATIVE_DISPLAY_LIMIT} of {len(all_narratives)} narratives "
            f"(serious cases shown first). Download ZIP for all."
        )
    for index, item in enumerate(narratives):
        with st.expander(f"Case {item['case_id']}"):
            st.code(writer.format_for_display(item["narrative"]), language="text")
            st.download_button(
                "Download narrative",
                item["narrative"].encode("utf-8"),
                file_name=f"case_{item['case_id'] or index + 1}.txt",
                mime="text/plain",
                key=f"narrative_dl_{index}",
            )
    if narratives:
        st.download_button(
            "Download all narratives ZIP",
            make_narrative_zip(narratives),
            file_name="icsr_narratives.zip",
            mime="application/zip",
        )


def render_deadline_tab(results: dict, formatter: OutputFormatter):
    st.subheader(f"Deadline status as of {pd.Timestamp.today().date()}")
    st.info(
        "**All 7-day and 15-day deadlines assume the reported reaction is unexpected per ICH E2A.** "
        "FAERS/openFDA does not contain product labeling data needed to verify listedness. "
        "Confirm expectedness against approved product labeling before regulatory submission."
    )
    deadlines_df = results["deadlines_df"]
    display = formatter.dataframe_to_display(
        deadlines_df,
        [
            "primaryid",
            "event_pt",
            "outcome_label",
            "receive_date",
            "deadline_days",
            "deadline_date",
            "days_remaining",
            "deadline_status",
            "rule_reference",
        ],
    )
    if "days_remaining" in display.columns:
        display = display.copy()
        display["days_remaining"] = display["days_remaining"].apply(
            lambda x: max(0, min(int(x), 90)) if isinstance(x, (int, float)) and not pd.isna(x) else 0
        )
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "days_remaining": st.column_config.ProgressColumn(
                "Days Remaining",
                help="Days until regulatory reporting deadline",
                format="%d days",
                min_value=0,
                max_value=90,
            ),
            "deadline_status": st.column_config.TextColumn(
                "Status",
                help="OVERDUE = past deadline | DUE SOON = <=3 days | ON TRACK = >3 days remaining",
            ),
            "receive_date": st.column_config.DateColumn("Receive Date"),
            "deadline_date": st.column_config.DateColumn("Deadline"),
        },
    )
    if not deadlines_df.empty:
        priority = {code: i for i, code in enumerate(["DE", "LT", "HO", "DS", "CA", "OT"])}
        worst_row = deadlines_df.copy()
        worst_row["_priority"] = worst_row["outcome_code"].map(lambda c: priority.get(c, 99))
        worst = worst_row.sort_values("_priority").iloc[0]
        st.caption(
            "Regional comparison based on worst-case outcome in batch: "
            f"**{worst.get('outcome_label', worst.get('outcome_code', 'Unknown'))}**"
        )
        regional = DeadlineCalculator().get_regional_deadlines(
            worst.get("outcome_code", ""), bool(worst.get("serious", False))
        )
        st.dataframe(pd.DataFrame(regional), use_container_width=True, hide_index=True)
    st.download_button(
        "Download deadline CSV",
        deadlines_df.to_csv(index=False).encode("utf-8"),
        file_name="deadline_report.csv",
        mime="text/csv",
    )


def render_ner_tab():
    def trigger_analysis(selected_drug):
        st.session_state.drug_input = selected_drug
        st.session_state.run_requested = True

    st.subheader("Free-Text Clinical NER")
    st.caption("Paste any clinical note, adverse event description, or ICSR text. Entities will be extracted using spaCy NLP.")

    SAMPLE_TEXT = (
        "A 54-year-old male patient was prescribed warfarin 5mg daily for atrial fibrillation. "
        "After 3 weeks he developed severe gastrointestinal haemorrhage and was hospitalised. "
        "Liver enzymes were elevated. Warfarin was discontinued and outcome was recovery."
    )

    if "ner_text" not in st.session_state:
        st.session_state.ner_text = ""

    if st.button("Use sample text"):
        st.session_state.ner_text = SAMPLE_TEXT
        st.session_state.ner_text_area = SAMPLE_TEXT
        st.rerun()

    text_input = st.text_area(
        "Clinical text input",
        value=st.session_state.ner_text,
        height=160,
        help="Supports clinical notes, adverse event narratives, or any medical free text.",
        key="ner_text_area",
    )

    if st.button("Extract Entities", type="primary"):
        if not text_input or not text_input.strip():
            st.warning("Please enter some clinical text.")
            return

        with st.status("Running spaCy NER pipeline...", expanded=True) as status:
            status.write("Loading spaCy model and tokenizer...")
            extractor = NERExtractor()
            status.write("Extracting drugs, adverse event terms, demographics, and SOC matches...")
            result = extractor.extract_entities(text_input)
            status.update(label="NER extraction complete", state="complete", expanded=False)

        col1, col2, col3 = st.columns(3)
        col1.metric("Drugs identified", len(result["drugs"]))
        col2.metric("AE terms extracted", len(result["ae_terms"]))
        col3.metric("SOC classifications", len(result["soc_classifications"]))

        st.write("")
        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Identified Drug Names**")
            if result["drugs"]:
                for drug in result["drugs"]:
                    st.markdown(f"<span class='badge badge-monitor'>Drug: {drug}</span>", unsafe_allow_html=True)
                suggested = result["drugs"][0]
                st.button(f"Search FAERS for '{suggested}'", on_click=trigger_analysis, args=(suggested,))
            else:
                st.info("No drug names detected")

        with c2:
            st.markdown("**Adverse Event Terms**")
            if result["ae_terms"]:
                for ae_term in result["ae_terms"][:10]:
                    st.markdown(f"<span class='badge badge-signal'>AE: {ae_term}</span>", unsafe_allow_html=True)
            else:
                st.info("No AE terms detected")

        st.write("")
        st.markdown("**System-Organ Class Classifications**")
        if result["soc_classifications"]:
            for hit in result["soc_classifications"]:
                terms = ", ".join(hit["matched_terms"])
                st.markdown(
                    f"<div class='pv-card'><strong>{hit['soc'].title()}</strong> - matched: {terms}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.info("No SOC patterns matched")

        if result.get("demographics"):
            st.markdown("**Extracted Demographics**")
            st.json(result["demographics"])


def render_e2b_tab(results: dict):
    exports = results["e2b_exports"]
    st.markdown(
        "<div class='pv-card'><strong>ICH E2B(R3) XML Export</strong>"
        "<p>Each export contains a structured XML case safety report for portfolio demonstration. "
        "Additional sender, receiver, indication, and time-to-onset fields are required before regulatory submission.</p>"
        "</div>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Per-reaction recovery status is taken directly from the openFDA `reactionoutcome` field when available. "
        "Where absent from the source report, outcomes default to 'unknown' (code 6). "
        "Patient age is parsed from the FAERS formatted string; verify against source data before submission."
    )
    if not exports:
        st.info("No E2B exports generated.")
        return
    st.metric("Cases exported", len(exports))
    for index, item in enumerate(exports):
        case_id = item.get("case_id") or f"UNKNOWN-{index + 1}"
        with st.expander(f"Case {case_id} - XML"):
            st.code(item["xml"], language="xml")
            st.download_button(
                "Download XML",
                item["xml"].encode("utf-8"),
                file_name=f"e2b_case_{case_id}.xml",
                mime="application/xml",
                key=f"e2b_dl_{index}",
            )


def render_audit_tab(results: dict):
    st.subheader("Current run")
    st.json(results["run_summary"])
    entries = load_audit_entries()
    if entries.empty:
        st.info("No audit entries recorded yet")
    else:
        st.dataframe(entries, use_container_width=True, hide_index=True)
    path = Path(AUDIT_LOG_PATH)
    if path.exists():
        st.download_button("Download audit JSONL", path.read_bytes(), file_name="trace_log.jsonl", mime="application/jsonl")


def main():
    inject_css()
    validator = InputValidator()
    formatter = OutputFormatter()

    st.sidebar.markdown(f"## {APP_NAME}")
    st.sidebar.caption(APP_SUBTITLE)
    st.sidebar.warning(
        "**Clinical Decision Support Only**\n\n"
        "PV-Trace outputs are generated from FAERS voluntary reports and are **not** "
        "a substitute for qualified pharmacovigilance physician review. All signals, "
        "narratives, and E2B exports require medical review before regulatory submission. "
        "FAERS data reflects reports, not confirmed causality.",
        icon=None,
    )
    st.sidebar.divider()

    with st.sidebar.form(key="drug_search_form"):
        drug_name = st.text_input(
            "Drug name",
            key="drug_input",
            placeholder="e.g. ibuprofen, warfarin",
        )
        analyze = st.form_submit_button("Analyze Drug", type="primary", use_container_width=True)

    st.sidebar.divider()
    st.sidebar.markdown(
        f"""
<div style='font-size:0.8rem;color:{COLOR_MUTED}'>
<strong style='color:{COLOR_TEXT}'>Signal Criteria</strong><br>
WHO-UMC / Evans<br><br>
<span style='color:{COLOR_PRIMARY}'>PRR >= {PRR_THRESHOLD:.1f}</span> &nbsp;
<span style='color:{COLOR_PRIMARY}'>Chi2 >= {CHI2_THRESHOLD:.1f}</span> &nbsp;
<span style='color:{COLOR_PRIMARY}'>n >= {MIN_CASE_COUNT}</span>
</div>
""",
        unsafe_allow_html=True,
    )

    st.sidebar.divider()
    st.sidebar.markdown(
        f"""
<div style='font-size:0.75rem;color:{COLOR_MUTED}'>
openFDA FAERS live<br>
WHO-UMC signal model<br>
ICH E2A deadline engine<br>
spaCy en_core_web_sm<br>
ICH E2B(R3) XML export
</div>
""",
        unsafe_allow_html=True,
    )

    st.sidebar.divider()
    st.sidebar.caption("Data: FDA FAERS | Built by Aruri Gowtham")

    if "results" not in st.session_state:
        st.session_state.results = None
    if "last_drug" not in st.session_state:
        st.session_state.last_drug = None

    should_run = analyze or st.session_state.pop("run_requested", False)
    if should_run:
        is_valid, message = validator.validate_drug_name(drug_name)
        if not is_valid:
            st.warning(message)
        else:
            clean_drug = validator.sanitize_drug_name(drug_name)
            try:
                results = run_pipeline(clean_drug)
                if results["events_df"].empty:
                    st.warning(f"No cases found for {clean_drug} in FAERS")
                st.session_state.results = results
                st.session_state.last_drug = clean_drug
            except Exception as error:
                st.error(str(error))
                if st.button("Retry"):
                    st.session_state.run_requested = True
                    st.rerun()

    if not st.session_state.results:
        render_landing()
        st.write("")
        with st.expander("Try the NER Extractor (no drug search needed)", expanded=False):
            render_ner_tab()
        return

    tabs = st.tabs(
        ["Signal Detection", "Clinical Signals", "ICSR Narratives", "Deadlines", "NER Extractor", "E2B Export", "Audit Trail"]
    )
    with tabs[0]:
        render_signal_tab(st.session_state.results, formatter, st.session_state.last_drug)
    with tabs[1]:
        render_clinical_tab(st.session_state.results)
    with tabs[2]:
        render_narrative_tab(st.session_state.results)
    with tabs[3]:
        render_deadline_tab(st.session_state.results, formatter)
    with tabs[4]:
        render_ner_tab()
    with tabs[5]:
        render_e2b_tab(st.session_state.results)
    with tabs[6]:
        render_audit_tab(st.session_state.results)


if __name__ == "__main__":
    main()
