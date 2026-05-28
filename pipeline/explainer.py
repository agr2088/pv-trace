"""
Clinical signal explanation using Hugging Face free Inference API.
Falls back to deterministic template if HF_TOKEN is not set or API is down.
"""

import requests
import pandas as pd

from config.settings import (
    HF_EXPLAIN_MAX_TOKENS,
    HF_EXPLAIN_TIMEOUT,
    HF_INFERENCE_URL,
    HF_TOKEN,
    PRR_THRESHOLD,
)


class ClinicalExplainer:
    """Generate clinical explanations for PV signals with deterministic fallback."""

    def _build_prompt(self, drug: str, event: str, prr: float, case_count: int, is_signal: bool) -> str:
        status = "a confirmed safety signal" if is_signal else "a monitored association (below signal threshold)"
        prr_value = prr if prr is not None else 0.0
        return (
            "You are a pharmacovigilance medical reviewer. "
            "Summarize this drug safety finding in 2 clinical sentences for a safety reviewer: "
            f"Drug: {drug}. Adverse event: {event}. "
            f"Cases reported: {case_count}. PRR: {prr_value:.2f}. "
            f"WHO-UMC signal threshold PRR >= {PRR_THRESHOLD:.1f}. "
            f"Classification: {status}."
        )

    def _call_hf_api(self, prompt: str) -> str | None:
        if not HF_TOKEN:
            return None
        try:
            response = requests.post(
                HF_INFERENCE_URL,
                headers={"Authorization": f"Bearer {HF_TOKEN}"},
                json={
                    "inputs": prompt,
                    "parameters": {
                        "max_new_tokens": HF_EXPLAIN_MAX_TOKENS,
                        "do_sample": False,
                    },
                },
                timeout=HF_EXPLAIN_TIMEOUT,
            )
            if response.status_code == 200:
                data = response.json()
                if isinstance(data, list) and data:
                    return str(data[0].get("generated_text", "")).strip()
        except Exception:
            pass
        return None

    def _template_explanation(self, drug: str, event: str, prr: float, case_count: int, is_signal: bool) -> str:
        prr_value = prr if prr is not None else 0.0
        if is_signal:
            return (
                f"A statistical safety signal was detected: {drug} and {event} "
                f"({case_count} cases, PRR {prr_value:.2f}) exceeds the WHO-UMC threshold of "
                f"{PRR_THRESHOLD:.1f}. Clinical causality assessment and medical review are "
                "recommended per Evans criteria before regulatory reporting."
            )
        return (
            f"{drug} shows {case_count} reported cases of {event} (PRR {prr_value:.2f}), "
            f"which does not meet WHO-UMC signal criteria (threshold: PRR >= {PRR_THRESHOLD:.1f}). "
            "Continued routine monitoring is recommended per standard pharmacovigilance practice."
        )

    def explain_signal(self, drug: str, event: str, prr: float, case_count: int, is_signal: bool) -> str:
        prompt = self._build_prompt(drug, event, prr, case_count, is_signal)
        ai_result = self._call_hf_api(prompt)
        if ai_result and len(ai_result) > 20:
            return ai_result
        return self._template_explanation(drug, event, prr, case_count, is_signal)

    def explain_batch(self, signals_df: pd.DataFrame, drug_name: str) -> pd.DataFrame:
        if signals_df.empty:
            output = signals_df.copy()
            output["explanation"] = []
            return output
        output = signals_df.copy()
        output["explanation"] = output.apply(
            lambda row: self.explain_signal(
                drug_name,
                row.get("event_pt", ""),
                row.get("prr"),
                int(row.get("case_count", 0)),
                bool(row.get("is_signal", False)),
            ),
            axis=1,
        )
        return output
