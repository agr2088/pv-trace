# PV-Trace

**Pharmacovigilance Signal Intelligence System — The Signal Station**

PV-Trace is a full-stack drug safety platform that pulls live adverse event reports from FDA FAERS, detects safety signals using WHO-UMC disproportionality criteria, generates ICH-structured case narratives, assigns regional reporting deadlines, and exports E2B(R3)-style XML — all in a single Streamlit dashboard built with a monitoring-console visual identity.

---

## Live Demo

[![Open in Streamlit](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://pv-trace.streamlit.app)

---

## Signal Station Dashboard

The redesigned dashboard ("The Signal Station") uses a monitoring-console visual identity with seven named stations, each with a distinct visualization:

| Station | Tab Name | What It Shows |
|---|---|---|
| **I — The Radar** | The Radar | Polar scatter plot with CSS sweep overlay; blip size = case count, radial distance = log(PRR), color = signal status |
| **II — Decode** | Decode | Side-by-side decode strip: raw signal metrics → plain-language clinical explanation |
| **III — Transcript** | Transcript | Console-transcript frame with blinking cursor; ICH E2D ICSR narratives |
| **IV — Countdown** | Countdown | Radial countdown gauges per case; deadline urgency with color-coded fill |
| **V — Packet** | Packet | E2B(R3) XML export with clickable segment diagram (Patient/Drug/Reaction/Outcome/Sender) |
| **VI — Decoder** | Decoder | Free-text clinical NER with inline entity highlighting (drugs, AE terms, dates) |
| **VII — Flight Recorder** | Flight Recorder | Hash-chained audit trail as horizontal tape with LED status indicator |

### Design System

- **Typography:** Space Grotesk (headings), IBM Plex Sans (body), JetBrains Mono (data/mono)
- **Color ladder:** Phosphor green (signal confirmed) → Amber trace (borderline/approaching) → Crimson alert (overdue/danger)
- **Header LED strip:** Station activity indicators — green = data loaded, dark = inactive
- **Clinical warning banner:** Persistent, non-dismissible safety notice
- **Animations:** CSS sweep line, blinking cursor, LED pulse — all respect `prefers-reduced-motion`

---

## What It Does

Type a drug name. PV-Trace runs a 7-stage pipeline and surfaces everything a pharmacovigilance reviewer needs:

| Stage | What Happens |
|---|---|
| **FAERS Ingestion** | Pulls up to 500 live case reports from openFDA per query |
| **Signal Detection** | Calculates PRR, ROR, EBGM, Chi² across all reported adverse events |
| **Clinical Explanation** | AI-generated signal interpretation via Hugging Face `flan-t5-base` |
| **ICSR Narratives** | Structured ICH E2D case narratives for each serious case |
| **Deadline Calculator** | 7 / 15 / 90-day ICH E2A rules with 4-region comparison |
| **E2B Export** | ICH E2B(R3)-style XML for case submissions |
| **NER Extractor** | spaCy biomedical NER for clinical free text (standalone) |

Every run is logged to an append-only JSONL audit trail with SHA-256 hash chaining and tamper detection.

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
| Dashboard | Streamlit ≥ 1.32 with custom Signal Station theme |
| Data source | openFDA FAERS API (live, 500 reports/query) |
| Signal statistics | NumPy · SciPy · Pandas |
| NLP / NER | spaCy `en_core_sci_sm` (biomedical), fallback `en_core_web_sm` |
| AI explainer | Hugging Face Inference API · `google/flan-t5-base` (free tier) |
| Charts | Plotly (polar radar, countdown gauges) |
| Design system | Custom CSS (scanline texture, phosphor borders, animations) |
| XML export | `xml.etree.ElementTree` (stdlib) |
| Audit trail | Append-only JSONL · SHA-256 hash chain · tamper detection |
| Testing | Pytest · 42 unit tests |

---

## Run Locally

```bash
git clone https://github.com/agr2088/pv-trace
cd pv-trace
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with your Hugging Face token:

```
HF_TOKEN=hf_your_token_here
```

Get one at [huggingface.co](https://huggingface.co) → Settings → Access Tokens → New token (read).

```bash
streamlit run app.py
```

Open [http://localhost:8501](http://localhost:8501)

---

## NER Models

PV-Trace uses two spaCy models for the standalone NER extractor:

| Model | Package | Use Case |
|---|---|---|
| `en_core_sci_sm` | scispaCy (biomedical) | Primary — extracts drug names, AE terms, demographics |
| `en_core_web_sm` | spaCy (general) | Fallback — SOC keyword matching only when scispaCy unavailable |

Models are downloaded automatically on first run via `requirements.txt`.

---

## Project Structure

```
pv-trace/
├── app.py                        # Streamlit dashboard — Signal Station entry point
├── dashboard/
│   ├── __init__.py
│   └── theme.py                  # Design system: tokens, CSS, 18 HTML component builders
├── config/
│   ├── __init__.py
│   └── settings.py               # Thresholds, colors, API settings, regional rules
├── pipeline/
│   ├── __init__.py
│   ├── ingestor.py               # openFDA FAERS data ingestion
│   ├── signal_detector.py        # PRR / ROR / EBGM / Chi² calculations
│   ├── explainer.py              # HF Inference API clinical explainer
│   ├── narrative_writer.py       # ICH E2D ICSR narrative generator
│   ├── deadline_calculator.py    # ICH E2A regional deadline engine
│   ├── e2b_exporter.py           # ICH E2B(R3) XML exporter
│   └── ner_extractor.py          # Biomedical NER entity extractor
├── audit/
│   ├── logger.py                 # Append-only JSONL audit trail with hash chain
│   └── .gitkeep
├── utils/
│   ├── __init__.py
│   ├── formatters.py             # Display formatting helpers
│   └── validators.py             # Input sanitisation
├── tests/                        # 42 Pytest unit tests
│   ├── test_signal_detector.py
│   ├── test_deadline.py
│   ├── test_e2b_exporter.py
│   ├── test_explainer.py
│   ├── test_ingestor.py
│   ├── test_validators.py
│   ├── test_audit_logger.py
│   └── test_radar_overlay.py
├── .streamlit/
│   └── config.toml               # Streamlit dark theme + server config
├── requirements.txt
├── pytest.ini
├── .env.example                  # Environment template
└── .gitignore
```

---

## Running Tests

```bash
pytest -v
```

42 unit tests covering:

- **Signal detection** — PRR, ROR, Chi² thresholds, division-by-zero, deduplication
- **Deadline calculator** — death/serious/life-threatening/congenital rules, CDSCO differentiation, RI/OT outcomes
- **E2B exporter** — XML declaration, reactionoutcome field handling, batch limits
- **Explainer** — template fallback when no HF token
- **Ingestor** — multi-reaction parsing, narrative case ID extraction
- **Validators** — drug name validation, SQL injection rejection, sanitization
- **Audit logger** — hash chain integrity, tamper detection, chain-break regression
- **Radar overlay** — CSS positioning methods for sweep-line overlay

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

## Audit Trail

Every pipeline run is logged to an append-only JSONL file with SHA-256 hash chaining:

- Each entry includes a `prev_hash` linking to the previous entry
- `AuditLogger.verify_chain()` validates the entire chain
- Tamper detection: modifying any entry breaks the chain from that point forward
- Flight Recorder station visualizes chain status with LED indicator

---

## Design Philosophy

The Signal Station redesign prioritizes **honesty over aesthetics**:

- Real data only — all visualizations read from live pipeline output, never mocked
- Four mandatory disclosures are always visible on their stations:
  - **P0-3:** Noise-floor ring (background count methodology)
  - **P1-5:** Reactionoutcome note (per-recovery status source)
  - **P1-6:** Expectedness banner (ICH E2A assumption caveat)
  - **P1-7:** Extraction mode badge (NER vs. keyword fallback)
- Color always maps to a real state, never decoration
- Pipeline code is never modified — only presentation changes

---

## About

Built by **Aruri Gowtham** — Pharm.D, Data Science, PvPI ADR pharmacovigilance experience.

Demonstrates full drug safety workflow knowledge: live data ingestion, disproportionality statistics, clinical NLP, multi-region regulatory timeline logic, submission-format XML export, GxP-aligned audit trail design, and monitoring-console dashboard visualization.
