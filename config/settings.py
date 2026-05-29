"""Central configuration for PV-Trace."""

import os
from pathlib import Path as _Path

from dotenv import load_dotenv

load_dotenv()

# API settings for live FAERS data retrieval.
OPENFDA_BASE_URL = "https://api.fda.gov/drug/event.json"
OPENFDA_LIMIT = 500
API_TIMEOUT = 10

# Signal thresholds based on WHO-UMC and Evans criteria.
PRR_THRESHOLD = 2.0
ROR_THRESHOLD = 2.0
CHI2_THRESHOLD = 4.0
MIN_CASE_COUNT = 3

# Deadline rules based on ICH E2A expedited reporting windows.
FATAL_UNEXPECTED_DAYS = 7
SERIOUS_UNEXPECTED_DAYS = 15
NON_SERIOUS_DAYS = 90

# FAERS outcome code labels.
OUTCOME_CODES = {
    "DE": "Death",
    "HO": "Hospitalisation",
    "LT": "Life-threatening",
    "DS": "Disability",
    "CA": "Congenital anomaly",
    "OT": "Other serious",
}

# Outcomes treated as serious for reporting and deadline rules.
SERIOUS_OUTCOMES = ["DE", "HO", "LT", "DS", "CA"]

# Regulatory regions displayed in deadline comparison.
REGIONS = ["FDA (USA)", "EMA (Europe)", "CDSCO (India)"]

# Audit log storage path.
AUDIT_LOG_PATH = str(_Path(__file__).parent.parent / "audit" / "trace_log.jsonl")

# OpenFDA fallback and export limits.
FAERS_TOTAL_FALLBACK = 10000000
NARRATIVE_BATCH_LIMIT = 10
NARRATIVE_DISPLAY_LIMIT = 5
E2B_BATCH_LIMIT = 5
CACHE_TTL_SECONDS = 300
AUDIT_DISPLAY_LIMIT = 20

# Date parsing and formatting.
DATE_INPUT_FORMATS = ["%Y%m%d", "%Y-%m-%d", "%d/%m/%Y"]
DISPLAY_DATE_FORMAT = "%d-%b-%Y"
ISO_DATE_FORMAT = "%Y-%m-%d"

# Application identity and sample queries.
APP_NAME = "PV-Trace"
APP_PAGE_TITLE = "PV-Trace | Drug Safety Intelligence"
APP_SUBTITLE = "Signal Intelligence System"
EXAMPLE_DRUGS = ["Ibuprofen", "Warfarin", "Metformin", "Atorvastatin"]

# UI color tokens.
COLOR_BACKGROUND = "#0a0f1e"
COLOR_SIDEBAR = "#050a14"
COLOR_CARD = "#111827"
COLOR_CARD_ALT = "#0d1421"
COLOR_BORDER = "#1f2937"
COLOR_PRIMARY = "#00d4aa"
COLOR_WARNING = "#e2b86a"
COLOR_DANGER = "#ef4444"
COLOR_TEXT = "#e5e7eb"
COLOR_MUTED = "#94a3b8"
COLOR_SUCCESS = "#22c55e"
COLOR_INFO = "#3b82f6"

# Hugging Face free inference API.
HF_TOKEN = os.getenv("HF_TOKEN", "")
HF_EXPLAIN_MODEL = "google/flan-t5-base"
HF_INFERENCE_URL = f"https://api-inference.huggingface.co/models/{HF_EXPLAIN_MODEL}"
HF_EXPLAIN_TIMEOUT = 20
HF_EXPLAIN_MAX_TOKENS = 120

# NER model: use scispaCy biomedical model if available, fallback to general English.
SPACY_MODEL_PRIMARY = "en_core_sci_sm"
SPACY_MODEL_FALLBACK = "en_core_web_sm"

# Signal detector background scaling and ingestion behavior.
BACKGROUND_SCALE_FACTOR = 1.0
FETCH_ALL_REACTIONS = True

# Audit log rotation.
AUDIT_MAX_LINES = 5000

# UI animation timing.
LOADING_STEP_DELAY = 0.05

SOC_KEYWORDS = {
    "cardiac disorders": ["heart", "cardiac", "myocardial", "arrhythmia", "palpitation", "chest pain", "tachycardia"],
    "hepatobiliary disorders": ["liver", "hepatic", "hepatitis", "jaundice", "bilirubin", "transaminase"],
    "renal and urinary disorders": ["kidney", "renal", "creatinine", "proteinuria", "oliguria", "nephropathy"],
    "nervous system disorders": ["seizure", "headache", "dizziness", "confusion", "neuropathy", "tremor"],
    "gastrointestinal disorders": ["nausea", "vomiting", "diarrhoea", "diarrhea", "abdominal", "stomach", "gastric"],
    "skin and subcutaneous disorders": ["rash", "urticaria", "pruritus", "erythema", "skin", "dermatitis"],
    "respiratory disorders": ["dyspnoea", "dyspnea", "cough", "wheeze", "bronchospasm", "pneumonia"],
    "blood and lymphatic disorders": ["bleeding", "haemorrhage", "hemorrhage", "anaemia", "anemia", "thrombocytopenia"],
    "immune system disorders": ["anaphylaxis", "allergy", "hypersensitivity", "angioedema"],
    "musculoskeletal disorders": ["myalgia", "arthralgia", "muscle pain", "joint pain", "rhabdomyolysis"],
}

DRUG_ENTITY_LABELS = {"CHEMICAL", "SIMPLE_CHEMICAL", "DRUG"}
AE_ENTITY_LABELS = {"DISEASE", "SYNDROME", "PATHOLOGICAL_FORMATION", "SIGN_OR_SYMPTOM"}
FALLBACK_DRUG_ENTITY_LABELS = {"PRODUCT"}
FALLBACK_AE_ENTITY_LABELS = {"DISEASE"}

# Regional deadline rules (ICH E2A + regional adaptations).
REGIONAL_DEADLINE_RULES = {
    "FDA (USA)": {
        "fatal_days": 7,
        "life_threatening_days": 7,
        "serious_days": 15,
        "non_serious_days": 90,
        "reference": "21 CFR 312.32 / ICH E2A",
    },
    "EMA (Europe)": {
        "fatal_days": 7,
        "life_threatening_days": 7,
        "serious_days": 15,
        "non_serious_days": 90,
        "reference": "GVP Module VI / ICH E2A",
    },
    "CDSCO (India)": {
        "fatal_days": 7,
        "life_threatening_days": 15,
        "serious_days": 15,
        "non_serious_days": 90,
        "reference": "Schedule Y, D&C Act 1940",
    },
    "WHO-UMC": {
        "fatal_days": 7,
        "life_threatening_days": 7,
        "serious_days": 15,
        "non_serious_days": 90,
        "reference": "VigiBase / ICH E2A",
    },
}

# Outcome codes used by regional deadline logic.
FATAL_OUTCOME_CODES = {"DE"}
LIFE_THREATENING_CODES = {"LT"}
