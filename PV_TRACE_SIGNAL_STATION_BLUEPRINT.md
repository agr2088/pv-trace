# PV-Trace Dashboard — "The Signal Station" Blueprint

**Purpose of this document:** target design spec for a rebuilt `app.py`. Not code — a
blueprint to build against, same discipline as `PV_TRACE_MASTER_BLUEPRINT.md` and the
`ae-severity-model` dashboard blueprint before it. Build station by station, screenshot
after each, self-critique against §8 before calling it done.

Note on theme: `ae-severity-model` already used a royal-court metaphor. This is a
different project with a different job — live signal detection, not a trained model's
verdict — so it gets its own visual identity, not a reskin of the same one.

---

## 0. The concept, in one sentence

Disproportionality analysis is **watching for a signal against background noise** — a
real adverse-event spike has to be picked out from the ordinary rate of reports the way
a radar operator picks out a real contact from clutter, or a seismograph picks out a
real tremor from ambient vibration. PV-Trace runs live, every query, against a moving
target (openFDA's current data) — that's a monitoring console's job, not a court's or a
ledger's. Working title: **"The Signal Station."** Seven instruments on one console
instead of seven generic tabs.

This isn't decoration bolted onto the math — PRR/ROR are literally *observed rate over
expected rate*, which is exactly what a detector distinguishing signal from noise does.
The visual language should make that ratio visible, not just report it as a number.

---

## 1. Design tokens

### Color — 6 named hex values, distinct from the royal palette and from AI-default looks

| Token | Hex | Role |
|---|---|---|
| `--deep-radar` | `#0B1210` | Page background — near-black with a green undertone, CRT-off darkness |
| `--console-panel` | `#14231F` | Panel/card surfaces — dark teal-green, instrument-housing color |
| `--phosphor` | `#4CFFA0` | Primary signal color — active detections, confirmed signals, healthy state |
| `--amber-trace` | `#FFB74D` | Secondary/caution — borderline signals, warnings, approaching deadlines |
| `--alert-crimson` | `#FF4757` | Critical — fatal outcomes, confirmed serious signals, chain tamper |
| `--static-fog` | `#7A8C86` | Muted/inactive — background noise, non-signal events, disabled state |

Green-on-near-black reads as "instrument," not as the generic near-black + single acid
accent AI-design tell — the difference is a full green-amber-red *signal ladder*
(noise → caution → detection) used consistently everywhere, not one bright color
scattered decoratively. Every hex above maps to a real state a value can be in, not a
mood.

### Typography — 3 roles

| Role | Face | Use |
|---|---|---|
| Display | **Space Grotesk**, 500–700 | Station titles, big readouts, the PRR headline number |
| Body | **IBM Plex Sans** | Explanatory copy, narrative text, tooltips |
| Data / utility | **JetBrains Mono** | Every number: PRR/ROR/chi2, case counts, hashes, timestamps, coordinates |

Space Grotesk is geometric and slightly technical without being a display serif — reads
as instrumentation, not as a genre cliché (not the warm-cream editorial serif, not a
generic rounded UI sans). Paired with JetBrains Mono for every data value, so numbers
always look like readouts, never like decorative labels — this pairing *is* the
signature typographic move, same role the Cormorant/mono pairing played on the other
project, different execution because the subject is different.

```python
st.markdown("""
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700
&family=IBM+Plex+Sans:wght@400;500&family=JetBrains+Mono:wght@400;500;600&display=swap"
rel="stylesheet">
""", unsafe_allow_html=True)
```

### Layout concept

A console, not a document. Full-bleed dark background, thin phosphor-green 1px borders
on every panel (instrument-casing lines, not decorative rules), subtle scanline texture
as a low-opacity repeating CSS gradient overlay on the page background only (never on
top of text or data — readability first).

```
┌──────────────────────────────────────────────────────────┐
│ ⬤⬤⬤⬤⬤⬤⬤  PV-TRACE — SIGNAL STATION      [drug query____] │  ← 7 LEDs = 7 stations
├──────────────────────────────────────────────────────────┤
│ SIGNAL │ CLINICAL │ NARRATIVE │ DEADLINE │ E2B │ NER │ LOG │  ← tab bar, active = lit LED
├──────────────────────────────────────────────────────────┤
│                                                            │
│   Station content — dark console panels, phosphor          │
│   borders, JetBrains Mono for every number, radar/gauge     │
│   graphics only where they encode real math                │
│                                                            │
└──────────────────────────────────────────────────────────┘
```

No sidebar — same reasoning as before, and doubly true here: a live console shouldn't
split attention between a persistent side panel and the instrument you're reading.

### Signature element

**The Radar Sweep** — on the Signal station, every adverse-event term the pipeline
detected is plotted as a blip on a circular radar display: **radial distance from
center = log(PRR)** (farther out = stronger disproportionality), **blip size = case
count** (a in the 2×2 table), **blip color = signal status** on the phosphor →
amber → crimson ladder. A thin sweep line rotates continuously; when it passes over a
blip that meets `is_signal()`'s real criteria (PRR + ROR + chi² all past threshold),
that blip pulses once, brighter, exactly the moment the sweep crosses it. This is not
decorative motion — the radial position is the actual log-PRR value, and the "signal
lock" pulse fires only for blips the real backend flagged as a signal, so the graphic
*is* the detection, not an illustration of it.

---

## 2. Station I — Signal Detection ("The Radar")

Functional purpose: PRR/ROR/EBGM/chi², Evans criteria, the P0-3 background-count
disclosure. Design:

**Wow visualization #1 — The Radar Sweep** (§1 signature element, full detail here)

```python
import plotly.graph_objects as go
import numpy as np

fig = go.Figure()
for _, row in signals_df.iterrows():
    r = np.log10(max(row["prr"], 1.01))          # radial = log(PRR)
    theta = row["angle_slot"]                       # even spacing per event
    color = {"signal": "#4CFFA0", "borderline": "#FFB74D", "noise": "#7A8C86"}[row["status"]]
    fig.add_trace(go.Scatterpolar(
        r=[r], theta=[theta], mode="markers",
        marker=dict(size=8 + np.log1p(row["a"]) * 3, color=color,
                    line=dict(color="#0B1210", width=1)),
        name=row["event_pt"], hovertemplate=f"{row['event_pt']}<br>PRR={row['prr']:.2f}<br>a={row['a']}<extra></extra>",
    ))
fig.update_layout(
    polar=dict(bgcolor="#14231F",
               radialaxis=dict(color="#7A8C86", gridcolor="#1E332C"),
               angularaxis=dict(showticklabels=False, gridcolor="#1E332C")),
    paper_bgcolor="#0B1210", font=dict(family="JetBrains Mono", color="#4CFFA0"),
    showlegend=False,
)
```

The rotating sweep line itself is a thin CSS-animated conic-gradient overlay positioned
on top of the Plotly chart's div (a semi-transparent phosphor wedge, `animation: sweep
4s linear infinite`, `@keyframes sweep { to { transform: rotate(360deg); } }`) — kept
as a separate absolutely-positioned layer so the underlying data plot stays untouched
by the animation.

**Noise-floor disclosure ring**: per the P0-3 fix, background counts are real for the
top-K events and estimated for the rest. Render this as a **dashed ring** at a fixed
radius on the same radar, labeled in small mono caption text: "Reports outside this
ring: real FAERS background. Inside: population-rate estimate." This turns the
required disclosure into part of the instrument itself instead of a caption users can
skim past — the exact spot where "this number might be less trustworthy" needs to live
is right next to the number.

**Metrics readout row** below the radar: PRR / ROR / EBGM / chi² as four mono-font
"instrument cards," each with a small horizontal threshold bar (current value vs.
threshold line) rather than a bare number — makes "did this cross the line" visible at
a glance, not just computed.

---

## 3. Station II — Clinical Explainer ("Decode")

Functional purpose: HF flan-t5-base explanation with template fallback.

**Visualization #2 — Signal-to-plain-language decode strip**: render the raw
statistical readout (PRR, case count, event term) on the left in mono type under a
"RAW SIGNAL" label, and the AI-generated plain-language explanation on the right under
a "DECODED" label, connected by a thin animated dotted line that draws once on load
(CSS `stroke-dashoffset` transition, not a looping animation — an orchestrated
one-time reveal, not ambient motion). If the explainer fell back to the template path
(no HF token / API failure), label it plainly: "Template fallback — not model-
generated" in muted `--static-fog` text. Never let a template output look like it came
from the model; that's a trust issue, not a style one.

---

## 4. Station III — Narrative Writer ("Transcript")

Functional purpose: ICH E2D-style ICSR narrative text.

**Visualization #3**: render each generated narrative inside a console-transcript
frame — thin phosphor border, a small blinking cursor block at the end of the text on
first render (CSS animation, respects `prefers-reduced-motion`), monospace throughout
since this *is* a generated document a reviewer reads closely — Space Grotesk display
type would work against readability here, so this is the one station where mono runs
the whole block, not just the numbers. Case metadata (primaryid, drug, event, outcome)
sits in a compact header strip above the transcript, not interleaved into the prose.

---

## 5. Station IV — Deadline Calculator ("Countdown")

Functional purpose: ICH E2A 7/15/90-day windows, the P1-6 expectedness caveat.

**Wow visualization #4 — Countdown gauges**: one radial countdown gauge per case,
arc filling from `--phosphor` (plenty of time) through `--amber-trace` (approaching)
to `--alert-crimson` (overdue), with the days-remaining number in large mono type at
center. This is a direct, honest encoding of the actual deadline math — no
embellishment needed because urgency *is* the content here.

**The expectedness caveat** (P1-6) renders as a fixed banner at the top of the station,
same visibility standard as every other disclosure in this build: "All deadlines
assume the reported reaction is unexpected per ICH E2A... Confirm expectedness against
approved product labeling before regulatory submission." Not inside a gauge, not a
tooltip — plainly above the countdowns, since a reviewer needs this caveat before
trusting any single gauge, not after clicking into one.

---

## 6. Station V — E2B(R3) Export ("Packet")

Functional purpose: ichicsr-style XML per case, the P1-5 reactionoutcome fix.

**Visualization #5**: a compact "packet structure" diagram — a horizontal stack of
labeled segments (patient / drug / reaction / outcome / sender) representing the E2B
XML's actual structure, each segment clickable to reveal that section's real generated
XML in a mono code block below. This is diagram-as-navigation, not diagram-as-metaphor
— it's genuinely useful for someone checking whether a specific field populated
correctly. The reactionoutcome disclosure (P1-5) sits directly under the "reaction"
segment specifically, not as a global banner, since it's a per-reaction-field caveat.

---

## 7. Station VI — NER Extractor ("Decoder")

Functional purpose: scispaCy/spaCy free-text extraction, standalone tab.

**Visualization #6**: inline entity highlighting directly in the pasted case-note
text — drug names underlined in `--phosphor`, AE terms in `--amber-trace`, dates/ages
in `--static-fog`, each with a small label chip on hover. Below the highlighted text,
a plain badge states which extraction mode is active: "scispaCy (en_core_sci_sm)" or,
honestly per the P1-7 fix, "Fallback: SOC-keyword matching only — no biomedical NER
model loaded." This status badge is load-bearing, not decorative — a user relying on
this tab needs to know which extraction quality they're getting.

---

## 8. Station VII — Audit Trail ("The Flight Recorder")

Functional purpose: hash-chained JSONL, `verify_chain()`.

**Visualization #7**: styled as a black-box flight-recorder tape — a horizontal
scrolling strip of entries, each a small mono-text tile, connected edge-to-edge like
a physical tape reel. A status LED at the left end shows solid `--phosphor` (verified)
or blinking `--alert-crimson` (break detected), driven directly by the real
`verify_chain()` result — same non-negotiable rule as the wax seal on the other
project: **never mock or randomize this state.** On a detected break, the tile at the
break point gets a crimson border and the tape visually "cuts" at that point (a small
gap rendered between tiles) so the exact break location is spatially obvious.

---

## 9. Global chrome

- **Header LED strip**: 7 small circular indicators, one per station, next to the
  page title — lit phosphor-green for stations with fresh/valid data this session, dim
  `--static-fog` for stations not yet run. Gives a genuine "is the console alive"
  status at a glance, distinct from and more useful than a generic loading spinner.
- **Query bar**: drug name input + Fetch button in the header, not per-tab — one
  query drives all seven stations, so the input lives once, globally, at the top.
- **Cold-start / fetch status**: explicit status text during any live openFDA call —
  "Receiving transmission…" is acceptable flavor text since it's honest about what's
  happening (a live API call) rather than vague; pair it with a real progress
  indicator, not just the phrase alone.
- **Empty states**: before any query has run, each station shows a dim, muted
  version of its instrument shell with the caption "No signal acquired" in
  `--static-fog` — consistent language across all seven, not a different empty-state
  phrase per tab.
- **Responsive floor**: the radar and countdown gauges need to degrade to a simpler
  bar/number layout under ~500px width — test narrow before shipping, same as before.

---

## 10. Implementation notes

- **Libraries**: `streamlit`, `plotly` (radar scatter-polar, countdown gauges via
  `go.Indicator`). Sweep-line animation, packet diagram, and flight-recorder tape are
  hand-built inline SVG/CSS via `st.markdown(unsafe_allow_html=True)` — no new JS
  library.
- **File layout**: new `dashboard/theme.py` (or extend if one already exists from a
  prior pass) holding CSS/font injection and the SVG/HTML builder functions
  (`radar_sweep_overlay()`, `countdown_gauge()`, `flight_recorder_tape()`,
  `packet_diagram()`). Keep `app.py`'s pipeline orchestration (ingestor → signal
  detector → explainer → narrative → deadline → e2b → audit) untouched by the
  redesign — presentation layer only, same discipline as before.
- **Every disclosure required by the P0/P1 fixes gets a fixed, visible home in the
  design**, not a caption easy to scroll past: the noise-floor ring on the radar
  (P0-3), the reactionoutcome note under the E2B packet's reaction segment (P1-5), the
  expectedness banner above the deadline gauges (P1-6), the extraction-mode badge on
  NER (P1-7). This list is the actual acceptance criteria for "the redesign didn't
  regress the honesty work already done" — check it explicitly in §8.
- **Real data only, always.** The radar's signal-status color, the countdown gauge's
  fill, the flight-recorder LED — every one of these must read from the real pipeline
  output (`is_signal()`, `verify_chain()`, actual deadline math), never a placeholder
  or randomized demo state. This is the single most important carry-over lesson from
  the last build.
- **Test after each station**, same one-at-a-time discipline: build Signal, screenshot,
  critique, then Clinical, then Narrative, and so on — don't build all seven before
  looking at any of them.

---

## 11. Self-critique checklist before calling it done

1. [ ] Would this be mistaken for a generic dark-mode Streamlit template? If yes, the
   radar/countdown/tape/packet-diagram aren't distinctive enough — they're the whole
   point.
2. [ ] Does every phosphor/amber/crimson color instance map to a real state (signal
   status, deadline urgency, verification result), or has color crept in as generic
   decoration? Cut any instance of the latter.
3. [ ] Is the PRR/ROR/chi² headline legible and correct with the radar chart removed
   entirely? The instrument cards under the radar should carry the number on their
   own.
4. [ ] Does the flight-recorder LED and the radar's signal pulses reflect the *actual*
   `verify_chain()` and `is_signal()` output, never a mocked/randomized demo state?
5. [ ] Are all four required disclosures (P0-3 noise-floor ring, P1-5 reactionoutcome
   note, P1-6 expectedness banner, P1-7 extraction-mode badge) visibly present on
   their respective stations, not buried?
6. [ ] Sidebar-free, no cream+terracotta or near-black+single-neon-accent default
   bleeding in — the green/amber/crimson ladder is used consistently, not as one-off
   decoration.
7. [ ] Keyboard focus visible on the tab bar and query button; sweep-line and
   blinking-LED animations respect `prefers-reduced-motion` (instant-state swap
   instead).

---

*This is a target-state design spec, not a description of any current `app.py`. Build
against it station by station, screenshotting and checking against §11 as you go —
and treat §10's disclosure checklist as non-negotiable acceptance criteria: this
redesign exists to make the pipeline's real behavior more visible, not to paper over
it with a nicer theme.*
