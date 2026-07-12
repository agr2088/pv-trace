"""PV-Trace Streamlit dashboard — The Signal Station."""

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
    AUDIT_DISPLAY_LIMIT,
    AUDIT_LOG_PATH,
    BACKGROUND_EVENT_LIMIT,
    CACHE_TTL_SECONDS,
    CHI2_THRESHOLD,
    E2B_BATCH_LIMIT,
    EXAMPLE_DRUGS,
    MIN_CASE_COUNT,
    NARRATIVE_DISPLAY_LIMIT,
    PRR_THRESHOLD,
    ROR_THRESHOLD,
)
from dashboard.theme import (
    inject_theme,
    header_bar,
    clinical_warning_banner,
    empty_station_shell,
    metric_card,
    noise_floor_ring_label,
    sweep_overlay_html,
    PHOSPHOR,
    STATIC_FOG,
    AMBER_TRACE,
    ALERT_CRIMSON,
    CONSOLE_PANEL,
    DEEP_RADAR,
    GRID_LINE,
    FONT_MONO,
    SIGNAL_COLOR,
    EXAMPLE_DRUGS,
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
    initial_sidebar_state="collapsed",
)


def inject_css():
    st.markdown(inject_theme(), unsafe_allow_html=True)


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
            <div style='font-family:Space Grotesk,sans-serif;font-size:0.8rem;color:{PHOSPHOR};
                        letter-spacing:0.2em;text-transform:uppercase;margin-bottom:0.5rem'>
                Pharmacovigilance Signal Intelligence
            </div>
            <h1 style='font-family:Space Grotesk,sans-serif;font-size:2.4rem;font-weight:700;
                       margin:0;letter-spacing:0;color:#e5e7eb'>
                PV-Trace
            </h1>
            <p style='color:{STATIC_FOG};margin-top:0.5rem;font-size:1rem;
                      font-family:IBM Plex Sans,sans-serif'>
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
            f"<div class='station-panel'><strong style='color:{PHOSPHOR}'>{title}</strong>"
            f"<p style='color:{STATIC_FOG};font-size:0.85rem;margin-top:0.4rem'>{body}</p></div>",
            unsafe_allow_html=True,
        )

    st.write("")
    st.caption("Quick examples")
    example_cols = st.columns(len(EXAMPLE_DRUGS))
    for col, drug in zip(example_cols, EXAMPLE_DRUGS):
        col.button(drug, use_container_width=True, on_click=trigger_analysis, args=(drug,))

    st.write("")
    st.markdown(
        f"<p style='text-align:center;color:{STATIC_FOG};font-size:0.78rem'>"
        "Built by <strong>Aruri Gowtham</strong> | Pharm.D + PvPI ADR Experience | Data Science 9.0 CGPA"
        "</p>",
        unsafe_allow_html=True,
    )


def render_signal_tab(results: dict, formatter: OutputFormatter, drug_name: str):
    import numpy as np

    events_df = results["events_df"]
    signals_df = results["signals_df"]

    if signals_df.empty:
        st.markdown(empty_station_shell("No signal acquired"), unsafe_allow_html=True)
        return

    signal_count = int(signals_df["is_signal"].sum())
    highest_prr = signals_df["prr"].max()

    st.markdown(
        f'<div class="station-label">Station I — The Radar: {drug_name}</div>',
        unsafe_allow_html=True,
    )

    top_metrics = st.columns(4)
    top_metrics[0].metric("Total unique cases", events_df["primaryid"].nunique())
    top_metrics[1].metric("Signals detected", signal_count)
    top_metrics[2].metric("Highest PRR", f"{highest_prr:.2f}" if pd.notna(highest_prr) else "N/A")
    top_metrics[3].metric("Events analyzed", len(signals_df))

    bg = results.get("bg_metadata")
    if bg:
        st.markdown(
            noise_floor_ring_label(
                bg["events_with_background"],
                bg["events_excluded"],
                bg["bg_failures"],
            ),
            unsafe_allow_html=True,
        )

    radar_df = signals_df.head(20).copy()
    radar_df["r"] = np.log10(radar_df["prr"].clip(lower=1.01))
    radar_df["angle_slot"] = np.linspace(0, 360, len(radar_df), endpoint=False)
    radar_df["status"] = radar_df.apply(
        lambda row: "signal" if row["is_signal"]
        else ("borderline" if row["prr"] >= 1.0 else "noise"),
        axis=1,
    )

    fig = go.Figure()
    for _, row in radar_df.iterrows():
        color = SIGNAL_COLOR[row["status"]]
        fig.add_trace(go.Scatterpolar(
            r=[row["r"]],
            theta=[row["angle_slot"]],
            mode="markers",
            marker=dict(
                size=8 + np.log1p(row["case_count"]) * 2,
                color=color,
                line=dict(color=DEEP_RADAR, width=1),
            ),
            name=row["event_pt"],
            hovertemplate=(
                f"<b>{row['event_pt']}</b><br>"
                f"PRR={row['prr']:.2f}<br>"
                f"a={int(row['case_count'])}<br>"
                f"<extra></extra>"
            ),
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
        height=520,
        margin=dict(t=20, b=20, l=40, r=40),
    )

    st.markdown(
        '<div style="position:relative;">',
        unsafe_allow_html=True,
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(sweep_overlay_html(), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown(
        f'<div style="font-family:\'{FONT_MONO}\',monospace;font-size:0.72rem;'
        f'color:{STATIC_FOG};text-align:center;padding:0.2rem 0;">'
        f'&#9678; Radial distance = log(PRR) &middot; Blip size = case count &middot; '
        f'Green = signal &middot; Amber = borderline &middot; Gray = noise</div>',
        unsafe_allow_html=True,
    )

    st.markdown('<div class="station-label" style="margin-top:0.8rem;">Instrument Readout</div>',
                unsafe_allow_html=True)

    avg_prr = signals_df["prr"].mean() if not signals_df.empty else 0
    avg_ror = signals_df["ror"].mean() if not signals_df.empty else 0
    avg_ebgm = signals_df["ebgm"].dropna().mean() if not signals_df.empty else 0
    avg_chi2 = signals_df["chi2"].mean() if not signals_df.empty else 0

    readout = st.columns(4)
    readout[0].markdown(
        metric_card("PRR", f"{avg_prr:.2f}", avg_prr, PRR_THRESHOLD, f">= {PRR_THRESHOLD}"),
        unsafe_allow_html=True,
    )
    readout[1].markdown(
        metric_card("ROR", f"{avg_ror:.2f}", avg_ror, ROR_THRESHOLD, f">= {ROR_THRESHOLD}"),
        unsafe_allow_html=True,
    )
    readout[2].markdown(
        metric_card("EBGM", f"{avg_ebgm:.2f}", avg_ebgm, 2.0, ">= 2.0"),
        unsafe_allow_html=True,
    )
    readout[3].markdown(
        metric_card("Chi2", f"{avg_chi2:.2f}", avg_chi2, CHI2_THRESHOLD, f">= {CHI2_THRESHOLD}"),
        unsafe_allow_html=True,
    )

    st.markdown('<div class="station-label" style="margin-top:1rem;">Signal Detail Table</div>',
                unsafe_allow_html=True)

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
        display_df["EBGM"] = display_df["ebgm"].map(lambda v: f"{v:.2f}" if pd.notna(v) else "N/A")
        display_df["Chi2"] = display_df["chi2"].map(lambda v: f"{v:.2f}")
        display_df["Signal"] = display_df["is_signal"].map(formatter.format_signal_badge)
    table = formatter.dataframe_to_display(display_df, ["Event", "Cases", "PRR", "ROR", "EBGM", "Chi2", "Signal"])
    st.dataframe(
        table,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Cases": st.column_config.NumberColumn("Cases", format="%d"),
            "PRR": st.column_config.TextColumn("PRR (95% CI)", width="medium"),
            "ROR": st.column_config.TextColumn("ROR (95% CI)", width="medium"),
            "Signal": st.column_config.TextColumn("Signal Status"),
        },
    )

    if signal_count == 0:
        st.success(
            f"No signals meeting WHO-UMC criteria (PRR >= {PRR_THRESHOLD}, Chi2 >= {CHI2_THRESHOLD}, "
            f"n >= {MIN_CASE_COUNT}) were detected for {len(signals_df)} adverse event terms. "
            "Continue routine pharmacovigilance monitoring."
        )

    st.download_button(
        "Download signal CSV",
        signals_df.to_csv(index=False).encode("utf-8"),
        file_name=f"{drug_name.lower()}_signals.csv",
        mime="text/csv",
    )


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

    if "results" not in st.session_state:
        st.session_state.results = None
    if "last_drug" not in st.session_state:
        st.session_state.last_drug = None

    active = [False] * 7
    if st.session_state.results:
        active[0] = True
        active[1] = bool(
            not st.session_state.results["signals_df"].empty
            and st.session_state.results["signals_df"]["is_signal"].any()
        )
        active[2] = bool(st.session_state.results["narratives"])
        active[3] = not st.session_state.results["deadlines_df"].empty
        active[5] = bool(st.session_state.results["e2b_exports"])

    st.markdown(header_bar(active), unsafe_allow_html=True)
    st.markdown(clinical_warning_banner(), unsafe_allow_html=True)

    header_cols = st.columns([4, 1])
    with header_cols[0]:
        drug_name = st.text_input(
            "Drug name",
            key="drug_input",
            placeholder="e.g. ibuprofen, warfarin",
            label_visibility="collapsed",
        )
    with header_cols[1]:
        analyze = st.button("Analyze Drug", type="primary", use_container_width=True)

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

    tabs = st.tabs([
        "The Radar",
        "Decode",
        "Transcript",
        "Countdown",
        "Decoder",
        "Packet",
        "Flight Recorder",
    ])
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
