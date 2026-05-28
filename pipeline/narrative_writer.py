"""ICH E2D-style ICSR narrative generation."""

from datetime import date

import pandas as pd

from config.settings import NARRATIVE_BATCH_LIMIT, OUTCOME_CODES


class NarrativeWriter:
    """Generate deterministic ICSR narratives for pharmacovigilance review."""

    def generate_narrative(self, case: dict) -> str:
        age = case.get("age") or "unknown age"
        gender = case.get("gender") or "patient"
        dose = case.get("dose") or "unspecified dose"
        serious = bool(case.get("serious", False))
        outcome_label = case.get("outcome_label") or OUTCOME_CODES.get(case.get("outcome_code"), "Not specified")
        seriousness_basis = f" based on: {outcome_label}" if serious else ""
        return (
            f"ICSR Narrative - Case {case.get('primaryid', 'Unknown')}\n"
            f"Generated: {date.today().isoformat()} | Per ICH E2D Guideline\n\n"
            f"This case concerns a {age} {gender} who was administered {case.get('drug_name', 'unknown drug')} "
            f"({dose}). The patient subsequently experienced {case.get('event_pt', 'an adverse event')}, "
            f"with onset reported around {case.get('receive_date', 'an unknown date')}. The case was reported from "
            f"{case.get('reporter_country', 'Unknown')}.\n\n"
            f"The outcome was recorded as {outcome_label}. This case "
            f"{'meets' if serious else 'does not meet'} the criteria for serious adverse event reporting "
            f"under ICH E2A guidelines{seriousness_basis}.\n\n"
            "Causality assessment is pending medical review. This narrative was auto-generated per ICH E2D "
            "structure and requires pharmacovigilance physician review prior to regulatory submission."
        )

    def generate_batch(self, df: pd.DataFrame) -> list[dict]:
        narratives = []
        for _, row in df.drop_duplicates(subset=["primaryid"]).head(NARRATIVE_BATCH_LIMIT).iterrows():
            case = row.to_dict()
            case_id = str(case.get("primaryid") or "").strip() or f"UNKNOWN-{len(narratives) + 1}"
            narrative = self.generate_narrative({**case, "primaryid": case_id})
            narratives.append(
                {
                    "case_id": case_id,
                    "narrative": narrative,
                    "serious": bool(case.get("serious", False)),
                }
            )
        return narratives

    def format_for_display(self, narrative: str) -> str:
        return str(narrative).replace("\r\n", "\n").strip()
