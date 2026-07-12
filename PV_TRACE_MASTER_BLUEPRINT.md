# PV-Trace — Master Pipeline Blueprint

**Source of truth:** pulled directly from the live repository (`github.com/agr2088/pv-trace`),
file by file — `pipeline/ingestor.py`, `pipeline/signal_detector.py`, `pipeline/explainer.py`,
`pipeline/narrative_writer.py`, `pipeline/deadline_calculator.py`, `pipeline/e2b_exporter.py`,
`pipeline/ner_extractor.py`, `audit/logger.py`, `utils/validators.py`, `config/settings.py`,
`app.py`. Every threshold, formula, and field named below is what the code does today, cross-checked
against the FDA FAERS data model, WHO-UMC/Evans disproportionality methodology, ICH E2A/E2B(R3),
and 21 CFR Part 11 — not generic textbook PV theory.

**One-line mental model:** Pull live FAERS reports for a drug from openFDA → run WHO-UMC-style
disproportionality statistics per adverse event term → explain the signals in plain language →
write ICSR narratives → assign regulatory reporting deadlines → export E2B(R3)-style XML → log
every step for traceability. All in one live Streamlit run, no offline training step — this is a
statistics/rules pipeline, not a trained ML model like `ae-severity-model`.

---

## 1. System Architecture

```
                    ┌─────────────────────────────────────┐
                    │            DATA SOURCE                │
                    │   openFDA API — LIVE, every run        │
                    │   https://api.fda.gov/drug/event.json  │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 1 — INGESTOR                   │
                    │   pipeline/ingestor.py                 │
                    │   OpenFDAIngestor.fetch_drug_events()  │
                    │   Output: one row per (case, reaction)  │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 2 — SIGNAL DETECTOR             │
                    │   pipeline/signal_detector.py           │
                    │   PRR, ROR, EBGM, Chi², Evans criteria  │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 3 — CLINICAL EXPLAINER          │
                    │   pipeline/explainer.py                 │
                    │   HF flan-t5-base, template fallback    │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 4 — NARRATIVE WRITER            │
                    │   pipeline/narrative_writer.py          │
                    │   ICH E2D-style ICSR narrative text      │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 5 — DEADLINE CALCULATOR         │
                    │   pipeline/deadline_calculator.py       │
                    │   ICH E2A 7/15/90-day windows            │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 6 — E2B(R3) EXPORTER            │
                    │   pipeline/e2b_exporter.py               │
                    │   ichicsr XML per case                   │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 7 — AUDIT LOGGER                │
                    │   audit/logger.py                        │
                    │   JSONL, one entry per pipeline step      │
                    └────────────────┬────────────────────┘
                                     │
                                     ▼
                    ┌─────────────────────────────────────┐
                    │   STAGE 8 — DASHBOARD                   │
                    │   app.py (Streamlit, 7 tabs)             │
                    │   Signal | Clinical | Narrative | Deadline│
                    │   | NER | E2B | Audit                    │
                    └─────────────────────────────────────┘
```

There's a separate, standalone utility that doesn't sit in the main pipeline: `NERExtractor`
(§7) — it's driven from its own tab, not chained after ingestion, and is used to pull a
candidate drug name/AE terms out of free-text clinical notes.

---

## 2. Stage 1 — Data Ingestion (`pipeline/ingestor.py`, class `OpenFDAIngestor`)

### 2a. Live pull, every run

Every analysis run hits `https://api.fda.gov/drug/event.json` directly — there's no offline/bulk
FAERS mode here (that exists in the separate `ae-severity-model` project, not this one). Query:

```
search: patient.drug.medicinalproduct:"<drug_name>"
limit: 500  (OPENFDA_LIMIT)
```

A `requests.Session` with retry (3 attempts, exponential backoff on HTTP 429/500/502/503/504)
handles transient openFDA outages. `fetch_total_count()` makes a second, separate call
(`limit=1`) purely to read `meta.results.total` — the full openFDA database size, used later as
the background denominator in signal detection (§3). If that call fails, it falls back to a
hardcoded `FAERS_TOTAL_FALLBACK = 10,000,000`.

Results are cached client-side via Streamlit's `@st.cache_data(ttl=300)` — a repeated query for
the same drug within 5 minutes reuses the cached DataFrame instead of re-hitting openFDA.

### 2b. Row shape: one row per (case, reaction) — not one row per case

`FETCH_ALL_REACTIONS = True` means `_parse_report_all_reactions()` expands every FAERS report
into **one row per adverse-event term reported on that case**. A case with 3 reactions produces 3
rows sharing the same `primaryid`. This is a deliberate, correct choice for building the
event-level table the signal detector needs (§3) — but it means **`len(events_df)` is a reaction
count, not a case count**, and anything downstream that treats row-count as case-count needs to
dedup by `primaryid` first (the narrative writer does this correctly — see §5; the signal detector
does not — see the flaw note in §3).

### 2c. Per-row field extraction

| Field | Extraction logic |
|---|---|
| `primaryid` | `report["primaryid"]` |
| `drug_name` | the search term itself (not re-parsed from the report) |
| `event_pt` | `patient.reaction[i].reactionmeddrapt`, one row per reaction; falls back to `"Unspecified adverse event"` if the case has no reaction list |
| `outcome_code` | derived by `_extract_outcome_code()`, checking openFDA's seriousness flags in priority order: `seriousnessdeath→DE`, `seriousnesshospitalization→HO`, `seriousnesslifethreatening→LT`, `seriousnessdisabling→DS`, `seriousnesscongenitalanomali→CA`; if none set but `serious=="1"`, falls to `OT`; else checks an `outcomes` list (rarely populated by openFDA) |
| `outcome_label` | human-readable label from `OUTCOME_CODES` |
| `receive_date` | `report["receivedate"]`, raw FAERS date string |
| `reporter_country` | `primarysourcecountry`, fallback `occurcountry`, fallback `"Unknown"` |
| `serious` | `True` if `outcome_code` is in `SERIOUS_OUTCOMES`, or openFDA's own `serious=="1"` flag |
| `age` | formatted string like `"45-yr-old"` via `_extract_age()` (age unit codes 800/801→yr, 802→month, 803→week, 804→day) |
| `gender` | `"male"`/`"female"`/`"patient"` from `patientsex` (1/2/other) |
| `dose` | matched from `patient.drug[]` by fuzzy substring match on the drug name, `drugdosagetext` or `drugdosage` |

**Outcome codes, confirmed against FDA's own FAERS data dictionary:** the FDA data dictionary
defines seven outcome codes for the `OUTC_COD` field — death (`DE`), life-threatening (`LT`),
hospitalization (`HO`), disability (`DS`), congenital anomaly (`CA`), required intervention to
prevent permanent impairment (`RI`), and other serious important medical event (`OT`) — and notes
that <cite index="2-1">if a case has more than one outcome, all applicable codes are listed against it, and the value returned reflects the latest version of the case.</cite> <cite index="3-1">FDA's own reporting-outcomes documentation confirms that "serious" means one or more of death, hospitalization, life-threatening, disability, congenital anomaly, and/or other serious outcome was documented on the report.</cite> This repo's `SERIOUS_OUTCOMES = ["DE","HO","LT","DS","CA"]` list matches five of the six seriousness-triggering codes — `RI` (required intervention) is the one seriousness outcome not represented in the list or in `OUTCOME_CODES` at all, so a case whose only documented outcome is "required intervention to prevent permanent impairment" won't be picked up as serious by this pipeline.

---

## 3. Stage 2 — Signal Detection (`pipeline/signal_detector.py`, class `SignalDetector`)

### 3a. The four disproportionality statistics

All four are standard 2×2-contingency-table methods used in real-world pharmacovigilance signal
screening. <cite index="26-1">Disproportionality analysis is based on a two-by-two contingency table, using the occurrence of adverse events related to other drugs in the database as a proxy for background incidence.</cite> The canonical table:

|  | Event of interest | All other events |
|---|---|---|
| **Drug of interest** | a | b |
| **All other drugs** | c | d |

- **PRR** (Proportional Reporting Ratio): <cite index="26-1">defined as [a/(a+b)] / [c/(c+d)]</cite> — this repo's formula matches exactly, with a log-transformed 95% CI via the standard error formula `sqrt(1/a - 1/(a+b) + 1/c - 1/(c+d))`.
- **ROR** (Reporting Odds Ratio): <cite index="26-1">defined as (a/c)/(b/d) = ad/bc</cite> — this repo's `(a*d)/(b*c)` matches, with the standard `sqrt(1/a+1/b+1/c+1/d)` CI formula.
- **Chi-square**: computed via `scipy.stats.chi2_contingency` on the same 2×2 table, uncorrected (`correction=False`), matching the conventional Yates-uncorrected chi-square used alongside PRR in WHO-UMC/Evans screening.
- **EBGM** (Empirical Bayes Geometric Mean, simplified): the repo computes a shrinkage estimate `(a+0.5)/(expected+0.5)` where `expected = (a+b)(a+c)/total` — this is a simplified single-shrinkage-term approximation, not the full Multi-Item Gamma Poisson Shrinker (MGPS) that FDA and most PV vendors use in production. It moves in the right direction (pulls small-count ratios toward 1) but shouldn't be read as a true regulatory-grade EBGM value — label it "simplified EBGM" wherever it's displayed.

**Evans/WHO-UMC signal flag**: `is_signal()` requires `case_count ≥ 3` AND `PRR ≥ 2.0` AND
`chi2 ≥ 4.0` — this is the standard "rule of three" (minimum case count) combined with the classic
Evans PRR≥2/χ²≥4/cases≥3 screening rule that WHO-UMC-influenced disproportionality screening
commonly uses. The thresholds themselves are correctly implemented.

### 3b. Where the inputs to that formula come from — this is the part to verify carefully

The formula is textbook-correct. **The four counts fed into it are not**, in two specific ways:

**1. `a` and `b` are reaction-rows, not cases.** Per §2b, `events_df` has one row per
(case, reaction) pair. `analyze_drug()` uses `total_drug_rows = len(drug_events_df)` as the
denominator for `a+b`, and `a = event_counts[event_pt]` (a row count) — without deduplicating by
`primaryid` first. A case reporting 4 reactions contributes 4 rows to the drug total, inflating
`a+b` relative to the true case count, and a case that happens to report the event of interest
multiple times (rare, but possible with duplicate MedDRA terms) inflates `a` specifically. The
narrative writer (§5) correctly dedups by `primaryid` before processing — the signal detector
does not.

**2. The background count `c` is not real FAERS data when no explicit background is supplied —
and nothing in the current app ever supplies one.** `analyze_drug()` accepts an optional
`event_background_counts` dict — if given real per-event FAERS totals, `c` is calculated
correctly. If not given, it falls back to an estimate: *"assume background event rate = 1 per
10,000 FAERS reports."* That fallback is a fixed, made-up constant, not a real measurement.

The ingestor has a method built for exactly this purpose — `fetch_event_count(drug_name,
event_pt)`, which queries openFDA for the real total case count of a specific event term — but a
direct search of the codebase confirms **it is never called anywhere else in the project**, and
`app.py`'s single call site (`detector.analyze_drug(events_df, total_count)`) never passes
`event_background_counts`. The practical effect: **every PRR, ROR, EBGM, and chi-square value this
app has ever displayed was computed against a fabricated background count**, not a real
event-specific FAERS background. This is the single most consequential finding in this pass — see
§9 for the fix.

### 3c. Output

One row per distinct `event_pt` for the queried drug, sorted by PRR descending, with columns
`event_pt, case_count, prr, prr_lower, prr_upper, ror, ror_lower, ror_upper, ebgm, chi2, is_signal`.

---

## 4. Stage 3 — Clinical Explanation (`pipeline/explainer.py`, class `ClinicalExplainer`)

For each signal row, builds a short prompt (drug, event, case count, PRR, WHO-UMC threshold,
signal/non-signal status) and sends it to the Hugging Face free Inference API running
`google/flan-t5-base`, with a 20-second timeout and up to 120 generated tokens. If `HF_TOKEN`
isn't set, the API call is skipped entirely (no network call attempted); if the API call fails,
times out, or returns a suspiciously short response (≤20 characters), `explain_signal()` falls
back to a deterministic template that states the PRR, case count, WHO-UMC threshold comparison,
and a fixed recommendation ("clinical causality assessment... recommended per Evans criteria" for
signals, "continued routine monitoring" otherwise).

This fallback-first design is sound engineering — the dashboard never blocks or errors out because
a free-tier HF model is asleep or rate-limited. Worth being explicit about in any documentation:
the AI-generated explanation is a **plain-language restatement** of numbers already computed
upstream (§3), not an independent clinical judgment — flan-t5-base has no access to case-level
narratives, prior signals for the drug, or causality assessment; it's paraphrasing the PRR/case
count you already have.

---

## 5. Stage 4 — ICSR Narrative Generation (`pipeline/narrative_writer.py`, class `NarrativeWriter`)

Deduplicates `events_df` by `primaryid` first (`drop_duplicates(subset=["primaryid"])`) —
correctly collapsing the reaction-exploded rows from Stage 1 back to one row per case — then takes
the first `NARRATIVE_BATCH_LIMIT` (10) cases and generates a deterministic, template-based
narrative per case: age, gender, drug, dose, adverse event, onset/receive date, reporting country,
outcome, and a seriousness statement. Explicitly labeled in its own output as auto-generated and
requiring "pharmacovigilance physician review prior to regulatory submission" — this caveat is
present in the generated text itself, not just in documentation, which is the right way to surface
it to anyone reading an exported narrative out of context.

This stage doesn't use the HF model — it's fully deterministic string templating, referencing ICH
E2D narrative structure (the ICH guideline covering standardized ICSR narrative content) by name
in its own header line.

---

## 6. Stage 5 — Regulatory Deadline Assignment (`pipeline/deadline_calculator.py`, class `DeadlineCalculator`)

### 6a. What it actually computes

For every case, assigns a deadline based on outcome code and seriousness:

- `outcome_code` in `{DE}` or `{LT}` → **7 days**
- otherwise, if `serious=True` → **15 days**
- otherwise → **90 days**

Then computes `deadline_date = receive_date + deadline_days`, and a status of `OVERDUE` /
`DUE SOON` (≤3 days remaining) / `ON TRACK` relative to today. A second method,
`get_regional_deadlines()`, repeats this logic per region (FDA, EMA, CDSCO) using
`REGIONAL_DEADLINE_RULES`, with CDSCO correctly modeled as using 15 days (not 7) for
life-threatening-but-non-fatal cases, per the Indian Schedule Y reference cited in config.

### 6b. What ICH E2A actually requires — and the gap between that and what FAERS data can supply

Research confirms the 7/15-day windows themselves are right: <cite index="37-1">regulatory agencies should be notified as soon as possible but no later than 7 calendar days after first knowledge that a case qualifies as an unexpected fatal or life-threatening reaction, followed by as complete a report as possible within 8 additional calendar days, while non-fatal or life-threatening serious unexpected reactions must be filed no later than 15 calendar days.</cite>

The gap: **ICH E2A's 7/15-day expedited windows apply specifically to reactions that are both
serious *and* unexpected** (i.e., not already listed in the product's reference safety
information/label). <cite index="42-1">The sponsor-investigator must ensure the event meets all three definitions — suspected adverse reaction, unexpected, and serious — and if it does not meet all three, it should not be submitted as an expedited report.</cite> "Expectedness" is a comparison against a specific drug's approved labeling — it is not a field openFDA/FAERS exposes, and this pipeline has no reference-labeling dataset to compare against. So `deadline_calculator.py` is applying the 7/15-day rule to **all** serious cases regardless of whether they'd actually be classified as unexpected under a real sponsor's safety data exchange agreement. That's a reasonable, clearly-labeled simplification for a signal-intelligence tool (better to flag more cases as time-sensitive than fewer), but it should be described as *"deadline if this case were unexpected"*, not as a definitive regulatory deadline — the current UI/output doesn't make that caveat explicit.

Separately: the "90-day rule" for non-serious cases is framed in this pipeline as an individual
per-case deadline, parallel to the 7- and 15-day windows. In the actual regulations, non-serious
(or expected) cases don't have an individual-case expedited deadline at all — the 90-day figure
in `NON_SERIOUS_DAYS` in this codebase is a reasonable general orientation number, but it isn't
tied to any specific ICH E2A citation the way the 7- and 15-day rules are (the `_rule_reference()`
method's mapping of `90 → "ICH E2A §3.4"` should be checked against the actual E2A section
numbering rather than assumed — non-serious ADR handling in E2A is addressed in the context of
periodic reporting, not a standalone per-case deadline clause).

---

## 7. Stage 6 — E2B(R3)-Style XML Export (`pipeline/e2b_exporter.py`, class `E2BExporter`)

Builds an `ichicsr` root XML element per case with a message header (`messagetype`, `messagedate`,
`messageidentifier`) and a `safetyreport` block (report ID, source country, receive date,
seriousness flag, narrative, patient demographics, one drug element, one reaction element).
`serious` is correctly encoded as E2B's binary `1`/`2` (yes/no) convention.

Two elements don't match the real E2B(R3) data typing, worth knowing before treating this export
as submission-ready:

- **`patientonsetage`** is written as a formatted string like `"45-yr-old"` (straight from the
  ingestor's display-formatted `age` field, §2c) rather than a numeric value with a separate age
  unit code. <cite index="53-1">E2B(R3) age-type data elements use the HL7 Physical Quantity (PQ) data type, which is expressed as two separate attributes — a numeric value and a UCUM unit code — not a combined display string.</cite> A real E2B(R3) consumer expects a bare number plus a coded unit, not `"45-yr-old"`.
- **`reactionoutcome`** is written directly as the FAERS `outcome_code` (`"DE"`, `"HO"`, etc.).
  Real E2B(R3) `reactionoutcome` is a small coded value set (recovered/recovering, recovered with
  sequelae, not recovered, fatal, unknown, etc.) — a different code list than FAERS's `OUTC_COD`
  seriousness codes. Passing FAERS codes straight through means a real E2B(R3)-consuming system
  would reject or misinterpret that field.

Given the file's own class docstring already calls this "a simple E2B(R3)-compatible XML
structure" rather than claiming full schema conformance, this isn't a false claim — but it's worth
tightening: it's presentation-format-inspired by E2B(R3), not validated against the actual ICH
ICSR XML schema, and shouldn't be represented to anyone downstream as submission-ready without a
proper field mapping pass.

---

## 8. Stage 7 — Audit Trail (`audit/logger.py`, class `AuditLogger`)

Append-only JSONL, one line per pipeline step (`ingestion`, `signal_detection`,
`clinical_explanation`, `narrative_generation`, `deadline_calculation`, `e2b_export`,
`prediction`), each entry carrying a `run_id` (UUID per analysis run), drug name, step name,
status, arbitrary details dict, and UTC timestamp. Narrative entries store a SHA-256 hash of the
generated narrative text rather than the text itself — a reasonable way to prove a specific
narrative was produced at a specific time without duplicating potentially large text into the
audit file. Log rotation (`_rotate_if_needed`) halves the file once it exceeds 5000 lines, keeping
the more recent half.

Same finding as the `ae-severity-model` audit: this is a clean, working JSONL logger, but it's
plain append-only text — anyone with filesystem access can open and edit it with no way to detect
that it happened. <cite index="18-1">A Part 11 audit trail must be computer-generated, automatic, time-stamped, and tamper-evident, with no user — including admins — able to modify entries.</cite> Nothing in this repo's docstrings currently overclaims "GxP compliance," so there's no false claim to correct here — just a gap worth closing if this is ever positioned as more than a portfolio/demo tool (see §9 fix list).

---

## 9. Stage 8 — Dashboard (`app.py`, Streamlit, 7 tabs)

`run_pipeline(drug_name)` is the orchestrator: it runs all seven stages in sequence inside a single
`st.status()` block with a progress bar, logging each step as it completes, and returns a results
dict consumed by the tab renderers. Order: ingest → detect signals → explain → write narratives →
calculate deadlines → export E2B → summarize audit run.

| Tab | What it shows | Backed by |
|---|---|---|
| **Signal** | Sortable table of all event PRR/ROR/EBGM/chi2/signal-flag results for the queried drug | Stage 2 |
| **Clinical** | Plain-language explanations per signal | Stage 3 |
| **Narrative** | Generated ICSR narratives, downloadable as a zip of per-case `.txt` files | Stage 4 |
| **Deadline** | Regulatory deadline table with status (overdue/due soon/on track) and regional comparison | Stage 5 |
| **NER** | Standalone free-text extractor — not part of the drug-query pipeline; paste clinical text, get back extracted drugs/AE terms/SOC classifications/demographics | §10, independent |
| **E2B** | Generated XML per case, viewable/downloadable | Stage 6 |
| **Audit** | Last 20 audit log entries for the current session | Stage 7 |

`cached_fetch()` wraps the ingestor call in `@st.cache_data(ttl=300)` — repeated identical drug
queries within 5 minutes are served from cache rather than re-hitting openFDA, which is a sensible
rate-limit/latency mitigation for a free public API.

---

## 10. Standalone Utility — NER Extraction (`pipeline/ner_extractor.py`, class `NERExtractor`)

Not chained into `run_pipeline()` — driven from its own tab, taking arbitrary pasted clinical
free-text as input rather than FAERS data.

**Model selection**: tries `en_core_sci_sm` (scispaCy biomedical model) first; if not installed,
falls back to `en_core_web_sm` (general English spaCy). Which model loaded determines which entity
labels are treated as "drug" vs. "adverse event":

- Biomedical model: `DRUG_ENTITY_LABELS = {CHEMICAL, SIMPLE_CHEMICAL, DRUG}` for drugs,
  `AE_ENTITY_LABELS = {DISEASE, SYNDROME, PATHOLOGICAL_FORMATION, SIGN_OR_SYMPTOM}` for AE terms.
- Fallback model: `FALLBACK_DRUG_ENTITY_LABELS = {PRODUCT}`,
  `FALLBACK_AE_ENTITY_LABELS = {DISEASE}`.

**Worth checking directly in your deployed environment:** spaCy's general-purpose
`en_core_web_sm` model ships with a fixed, well-documented NER label set (`PERSON`, `ORG`, `GPE`,
`DATE`, `CARDINAL`, `PRODUCT`, `NORP`, `FAC`, `LOC`, `EVENT`, `LAW`, `LANGUAGE`, `WORK_OF_ART`,
`MONEY`, `PERCENT`, `QUANTITY`, `ORDINAL`, `TIME` — no `DISEASE` label). If that holds in your
deployed version, the fallback path's AE-term extraction via NER produces zero results whenever
scispaCy isn't installed (e.g., a fresh deploy where the scispaCy model download step failed
silently) — `PRODUCT` would still catch some drug names, but AE terms would come only from the
separate `SOC_KEYWORDS` keyword-matching pass (§10b), not from the NER pass at all. Confirm this
against the actual installed spaCy model version in your environment before relying on the
fallback path for AE extraction.

**SOC keyword layer**: independent of which spaCy model loaded, `extract_entities()` also runs a
plain substring match against `SOC_KEYWORDS` — ten MedDRA System Organ Class categories (cardiac,
hepatobiliary, renal, nervous system, GI, skin, respiratory, blood/lymphatic, immune,
musculoskeletal), each with a hand-picked keyword list. Matches contribute both an SOC
classification and additional AE terms. This layer works regardless of which NER model is active,
and is effectively the reliability backstop for AE-term extraction.

**Age/date extraction**: `CARDINAL` entities are checked for nearby context words (`year`, `yr`,
`old`, `age`) to guess which numbers represent patient age; `DATE` entities are collected as-is.
Both are heuristic, not validated against a structured date/age parser — reasonable for a
free-text triage aid, not for structured downstream use without a human check.

`suggest_drug_query()` returns the first extracted drug name as a candidate openFDA search
term — a plausible bridge from "paste a case note" to "auto-populate the drug field," though it
isn't currently wired to auto-populate the Signal tab's query box (worth confirming whether that
connection exists in your version, or whether it's a manual copy-paste step for the user today).

---

## 11. Full Configuration Reference (`config/settings.py`)

**Data source**
`OPENFDA_BASE_URL=https://api.fda.gov/drug/event.json` · `OPENFDA_LIMIT=500` · `API_TIMEOUT=10s` ·
`FAERS_TOTAL_FALLBACK=10,000,000` · `FETCH_ALL_REACTIONS=True`

**Signal thresholds**
`PRR_THRESHOLD=2.0` · `ROR_THRESHOLD=2.0` (defined but not actually used by `is_signal()`, which
checks only PRR + chi2 — see §12) · `CHI2_THRESHOLD=4.0` · `MIN_CASE_COUNT=3` ·
`BACKGROUND_SCALE_FACTOR=1.0` (defined, not referenced in `signal_detector.py` — check if this
was meant to be part of the background-count fix)

**Deadlines (ICH E2A)**
`FATAL_UNEXPECTED_DAYS=7` · `SERIOUS_UNEXPECTED_DAYS=15` · `NON_SERIOUS_DAYS=90` ·
`REGIONAL_DEADLINE_RULES` (FDA/EMA/CDSCO/WHO-UMC) · `FATAL_OUTCOME_CODES={DE}` ·
`LIFE_THREATENING_CODES={LT}`

**Outcome codes**
`OUTCOME_CODES` (DE/HO/LT/DS/CA/OT — missing RI, per §2c) · `SERIOUS_OUTCOMES=[DE,HO,LT,DS,CA]`

**AI explanation**
`HF_TOKEN` (from environment) · `HF_EXPLAIN_MODEL=google/flan-t5-base` ·
`HF_INFERENCE_URL` · `HF_EXPLAIN_TIMEOUT=20s` · `HF_EXPLAIN_MAX_TOKENS=120`

**NER**
`SPACY_MODEL_PRIMARY=en_core_sci_sm` · `SPACY_MODEL_FALLBACK=en_core_web_sm` ·
`DRUG_ENTITY_LABELS` / `AE_ENTITY_LABELS` / `FALLBACK_DRUG_ENTITY_LABELS` /
`FALLBACK_AE_ENTITY_LABELS` · `SOC_KEYWORDS` (10 SOC categories)

**Batching & display limits**
`NARRATIVE_BATCH_LIMIT=10` · `NARRATIVE_DISPLAY_LIMIT=5` · `E2B_BATCH_LIMIT=5` ·
`AUDIT_DISPLAY_LIMIT=20` · `CACHE_TTL_SECONDS=300`

**Audit**
`AUDIT_LOG_PATH=audit/trace_log.jsonl` · `AUDIT_MAX_LINES=5000`

**Dates**
`DATE_INPUT_FORMATS=["%Y%m%d","%Y-%m-%d","%d/%m/%Y"]` · `DISPLAY_DATE_FORMAT` · `ISO_DATE_FORMAT`

---

## 12. File-by-File Map

```
pv-trace/
├── app.py                        Streamlit dashboard — 7 tabs, orchestrates run_pipeline()
├── config/
│   └── settings.py               Every constant, threshold, path, and label mapping
├── pipeline/
│   ├── ingestor.py                Stage 1 — live openFDA pull, one row per (case, reaction)
│   ├── signal_detector.py         Stage 2 — PRR/ROR/EBGM/Chi2, Evans/WHO-UMC signal flag
│   ├── explainer.py               Stage 3 — HF flan-t5-base with deterministic fallback
│   ├── narrative_writer.py        Stage 4 — ICH E2D-style ICSR narrative text
│   ├── deadline_calculator.py     Stage 5 — ICH E2A 7/15/90-day + regional comparison
│   ├── e2b_exporter.py            Stage 6 — ichicsr-style XML per case
│   └── ner_extractor.py           Standalone — scispaCy/spaCy free-text extraction
├── audit/
│   └── logger.py                  Stage 7 — AuditLogger, JSONL append + rotation
├── utils/
│   ├── validators.py               Drug name / date input validation and sanitization
│   └── formatters.py               (referenced by app.py as OutputFormatter — not reviewed this pass)
└── tests/                          pytest suite: test_deadline, test_ingestor, test_signal_detector, test_validators
```

---

## 13. Findings From This Pass — Confirmed, Not Just Flagged

Unlike the earlier `ae-severity-model` blueprint, these aren't "things to check" — each one below
was verified directly against the code (grep + read), not inferred from documentation:

1. **Signal detection background counts are fabricated in every live run.** `fetch_event_count()`
   exists in `ingestor.py` to pull real per-event FAERS totals but is never called anywhere in the
   codebase; `app.py`'s only call to `analyze_drug()` never passes `event_background_counts`. So
   `c` in every PRR/ROR/EBGM/chi2 calculation this app has ever produced comes from the hardcoded
   "1 per 10,000 reports" fallback estimate, not real data. **This is the highest-priority fix** —
   it affects every number on the Signal tab.
2. **`a`/`b` in the signal detector are reaction-row counts, not case counts**, because
   `analyze_drug()` doesn't dedup `events_df` by `primaryid` before counting, while
   `narrative_writer.py` correctly does. Any drug where cases commonly report multiple reactions
   will have inflated `a+b` relative to the true case denominator.
3. **`RI` (required intervention) is missing from both `OUTCOME_CODES` and `SERIOUS_OUTCOMES`** —
   one of FAERS's six seriousness-triggering outcome codes isn't recognized as serious by this
   pipeline at all.
4. **`ROR_THRESHOLD` is defined in config but never read by `is_signal()`** — the signal flag
   currently only checks PRR and chi2 against their thresholds, not ROR. Either wire it in or
   remove the unused constant.
5. **`en_core_web_sm` (the NER fallback model) has no `DISEASE` label** in its standard tag set —
   worth confirming in your deployed environment, since if true, the fallback path's NER-based
   AE-term extraction silently returns nothing whenever scispaCy isn't available, leaving the
   SOC-keyword layer as the only working AE extraction path in that mode.
6. **E2B(R3) export fields don't match the real coded/typed data model** — `patientonsetage` is a
   display string (`"45-yr-old"`) instead of a numeric value + unit code, and `reactionoutcome`
   passes FAERS's `OUTC_COD` codes directly instead of E2B(R3)'s own reaction-outcome code list.
   Fine for a demo/portfolio export; not schema-conformant if ever positioned as submission-ready.
7. **ICH E2A 7/15-day deadlines are applied without an expectedness/listedness check**, because
   FAERS/openFDA data has no reference-labeling field to compare against — a structural data
   limitation, not a code bug, but one that should be stated explicitly wherever deadlines are
   displayed (e.g., "assumes unexpected — verify against product labeling").
8. **Audit log is plain append-only JSONL**, same gap as `ae-severity-model` — no tamper-evidence.
   Same fix applies: hash-chain each entry (see that project's blueprint §8 for the exact
   implementation pattern) if this is ever positioned as more than a demo audit trail.

---

*This blueprint reflects the code exactly as it exists in the cloned `main` branch at the time of
writing. If local changes haven't been pushed, re-pull before using this as a fix reference.*
