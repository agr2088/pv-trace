# PV-Trace

**Pharmacovigilance Signal Intelligence System**

PV-Trace is a full-stack drug safety platform that pulls live adverse event reports from FDA FAERS, detects safety signals using WHO-UMC disproportionality criteria, generates ICH-structured case narratives, assigns regional reporting deadlines, and exports E2B(R3)-style XML — all in a single Streamlit dashboard.

---

## Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pv-trace.streamlit.app)

---

## What It Does

Type a drug name. PV-Trace runs a 6-stage pipeline and surfaces everything a pharmacovigilance reviewer needs:

| Stage | What Happens |
|---|---|
| **FAERS Ingestion** | Pulls up to 500 live case reports from openFDA per query |
| **Signal Detection** | Calculates PRR, ROR, EBGM, Chi² across all reported adverse events |
| **Clinical Explanation** | AI-generated signal interpretation via Hugging Face `flan-t5-base` |
| **ICSR Narratives** | Structured ICH E2D case narratives for each serious case |
| **Deadline Calculator** | 7 / 15 / 90-day ICH E2A rules with 4-region comparison |
| **E2B Export** | ICH E2B(R3)-style XML for case submissions |

Every run is logged to an append-only JSONL audit trail with SHA-256 narrative hashes.

---

## Signal Detection Criteria

Uses WHO-UMC Evans disproportionality methodology. A drug-event pair is flagged as a **signal** when all three conditions are met simultaneously:

- PRR ≥ 2.0
- Chi-square ≥ 4.0
- Minimum 3 reported cases

ROR ≥ 2.0 is calculated as a supporting metric. Pairs below threshold are tracked as **monitored associations** for PSUR inclusion.

---

## Regional Deadline Rules (ICH E2A)

| Region | Fatal | Life-Threatening | Serious | Non-Serious |
|---|---|---|---|---|
| FDA (USA) | 7 days | 7 days | 15 days | 90 days |
| EMA (Europe) | 7 days | 7 days | 15 days | 90 days |
| CDSCO (India) | 7 days | 15 days | 15 days | 90 days |
| WHO-UMC | 7 days | 7 days | 15 days | 90 days |

> CDSCO (Schedule Y) does not apply the 7-day rule to life-threatening cases — mapped to 15 days.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Dashboard | Streamlit ≥ 1.32 |
| Data source | openFDA FAERS API (live, 500 reports/query) |
| Signal statistics | NumPy · SciPy · Pandas |
| NLP / NER | scispaCy `en_core_sci_sm` (biomedical), fallback `en_core_web_sm` |
| AI explainer | Hugging Face Inference API · `google/flan-t5-base` (free, no billing) |
| Charts | Plotly |
| XML export | `xml.etree.ElementTree` |
| Audit trail | Append-only JSONL · SHA-256 narrative hashing |
| Testing | Pytest · 14 unit tests |

---

## Run Locally

```bash
git clone https://github.com/agr2088/pv-trace
cd pv-trace
pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

Open [http://localhost:8502](http://localhost:8502)

Add your free Hugging Face token to `.env`:

```
HF_TOKEN=hf_your_token_here
```

Get it at [huggingface.co](https://huggingface.co) → Settings → Access Tokens → New token (read).

---

## Project Structure

```
pv-trace/
├── app.py                    # Streamlit dashboard (entry point)
├── config/
│   └── settings.py           # Thresholds, colors, API settings, regional rules
├── pipeline/
│   ├── ingestor.py           # openFDA FAERS data ingestion
│   ├── signal_detector.py    # PRR / ROR / EBGM / Chi² calculations
│   ├── explainer.py          # HF Inference API clinical explainer
│   ├── narrative_writer.py   # ICH E2D ICSR narrative generator
│   ├── deadline_calculator.py# ICH E2A regional deadline engine
│   ├── e2b_exporter.py       # ICH E2B(R3) XML exporter
│   └── ner_extractor.py      # Biomedical NER entity extractor
├── audit/
│   └── logger.py             # Append-only JSONL audit trail
├── utils/
│   ├── formatters.py         # Display formatting helpers
│   └── validators.py         # Input sanitisation
├── tests/                    # 14 Pytest unit tests
├── requirements.txt
└── .env                      # HF_TOKEN (not committed)
```

---

## Running Tests

```bash
pytest
```

14 unit tests cover signal detection thresholds, deadline calculation logic, and FAERS ingestion behaviour.

---

## Regulatory Framework

| Guideline | Applied In |
|---|---|
| ICH E2A | Deadline calculator — expedited reporting windows |
| ICH E2D | Narrative writer — ICSR structure |
| ICH E2B(R3) | XML exporter — case submission format |
| ICH E2E | Signal detection scope |
| WHO-UMC / Evans | PRR/ROR signal thresholds |
| FDA 21 CFR 312.32 | US regional deadline rules |
| EMA GVP Module VI | EU regional deadline rules |
| CDSCO Schedule Y | India regional deadline rules |

---

## About

Built by **Aruri Gowtham** — Pharm.D, Data Science, PvPI ADR pharmacovigilance experience.

Demonstrates full drug safety workflow knowledge: live data ingestion, disproportionality statistics, clinical NLP, multi-region regulatory timeline logic, submission-format XML export, and GxP-aligned audit trail design.
