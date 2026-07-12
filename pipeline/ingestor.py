"""openFDA FAERS ingestion utilities."""

import requests
import pandas as pd
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import (
    API_TIMEOUT,
    FAERS_TOTAL_FALLBACK,
    FETCH_ALL_REACTIONS,
    OPENFDA_BASE_URL,
    OPENFDA_LIMIT,
    OUTCOME_CODES,
    SERIOUS_OUTCOMES,
)


class OpenFDAIngestor:
    """Fetch and normalize adverse event reports from the openFDA drug event API."""

    def __init__(self):
        self.base_url = OPENFDA_BASE_URL
        self.limit = OPENFDA_LIMIT
        self.timeout = API_TIMEOUT
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1.0,
            status_forcelist=[429, 500, 502, 503, 504],
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    def fetch_drug_events(self, drug_name: str) -> pd.DataFrame:
        params = {
            "search": f'patient.drug.medicinalproduct:"{drug_name}"',
            "limit": self.limit,
        }
        try:
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            results = response.json().get("results", [])
        except requests.RequestException as error:
            raise Exception(f"openFDA API unavailable: {error}") from error

        rows = []
        for report in results:
            if FETCH_ALL_REACTIONS:
                rows.extend(self._parse_report_all_reactions(report, drug_name))
            else:
                rows.append(self._parse_report(report, drug_name))
        return pd.DataFrame(
            rows,
            columns=[
                "primaryid",
                "drug_name",
                "event_pt",
                "outcome_code",
                "outcome_label",
                "receive_date",
                "reporter_country",
                "serious",
                "age",
                "gender",
                "dose",
                "reaction_outcome",
            ],
        )

    def fetch_event_count(self, drug_name: str, event_pt: str) -> int:
        params = {
            "search": (
                f'patient.drug.medicinalproduct:"{drug_name}"'
                f' AND patient.reaction.reactionmeddrapt:"{event_pt}"'
            ),
            "limit": 1,
        }
        try:
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return int(response.json().get("meta", {}).get("results", {}).get("total", 0))
        except requests.RequestException:
            return 0

    def fetch_event_total_count(self, event_pt: str) -> int:
        params = {
            "search": f'patient.reaction.reactionmeddrapt:"{event_pt}"',
            "limit": 1,
        }
        try:
            response = self.session.get(self.base_url, params=params, timeout=self.timeout)
            response.raise_for_status()
            return int(response.json().get("meta", {}).get("results", {}).get("total", 0))
        except requests.RequestException:
            return 0

    def fetch_total_count(self) -> int:
        try:
            response = self.session.get(self.base_url, params={"limit": 1}, timeout=self.timeout)
            response.raise_for_status()
            return int(response.json().get("meta", {}).get("results", {}).get("total", FAERS_TOTAL_FALLBACK))
        except requests.RequestException:
            return FAERS_TOTAL_FALLBACK

    def _parse_report_all_reactions(self, report: dict, drug_name: str) -> list[dict]:
        """Return one row per reaction per case."""
        reactions = report.get("patient", {}).get("reaction", []) or []
        outcomes = report.get("seriousness", []) or report.get("patient", {}).get("patientdeath", [])
        outcome_code = self._extract_outcome_code(report, outcomes)
        base = {
            "primaryid": report.get("primaryid", ""),
            "drug_name": drug_name,
            "outcome_code": outcome_code,
            "outcome_label": OUTCOME_CODES.get(outcome_code, "Not specified"),
            "receive_date": report.get("receivedate", ""),
            "reporter_country": report.get("primarysourcecountry", report.get("occurcountry", "Unknown")),
            "serious": outcome_code in SERIOUS_OUTCOMES or str(report.get("serious", "")) == "1",
            "age": self._extract_age(report),
            "gender": self._extract_gender(report),
            "dose": self._extract_dose(report, drug_name),
        }
        if not reactions:
            return [{**base, "event_pt": "Unspecified adverse event", "reaction_outcome": ""}]
        return [
            {
                **base,
                "event_pt": reaction.get("reactionmeddrapt") or "Unspecified adverse event",
                "reaction_outcome": str(reaction.get("reactionoutcome", "")),
            }
            for reaction in reactions
        ]

    def _parse_report(self, report: dict, drug_name: str) -> dict:
        return self._parse_report_all_reactions(report, drug_name)[0]

    @staticmethod
    def _extract_event(reactions: list[dict]) -> str:
        if not reactions:
            return "Unspecified adverse event"
        return reactions[0].get("reactionmeddrapt") or "Unspecified adverse event"

    @staticmethod
    def _extract_outcome_code(report: dict, outcomes) -> str:
        if str(report.get("seriousnessdeath", "")) == "1":
            return "DE"
        if str(report.get("seriousnesshospitalization", "")) == "1":
            return "HO"
        if str(report.get("seriousnesslifethreatening", "")) == "1":
            return "LT"
        if str(report.get("seriousnessdisabling", "")) == "1":
            return "DS"
        if str(report.get("seriousnesscongenitalanomali", "")) == "1":
            return "CA"
        if str(report.get("serious", "")) == "1":
            return "OT"
        if isinstance(outcomes, list) and outcomes:
            code = outcomes[0].get("outcome") if isinstance(outcomes[0], dict) else str(outcomes[0])
            return code if code in OUTCOME_CODES else "OT"
        return "OT"

    @staticmethod
    def _extract_age(report: dict) -> str:
        patient = report.get("patient", {}) or {}
        age = patient.get("patientonsetage")
        unit = patient.get("patientonsetageunit", "")
        unit_label = {"800": "yr", "801": "yr", "802": "month", "803": "week", "804": "day"}.get(
            str(unit), "yr"
        )
        return f"{age}-{unit_label}-old" if age else "unknown age"

    @staticmethod
    def _extract_gender(report: dict) -> str:
        patient = report.get("patient", {}) or {}
        sex = str(patient.get("patientsex", "")).strip()
        return {"1": "male", "2": "female"}.get(sex, "patient")

    @staticmethod
    def _extract_dose(report: dict, drug_name: str) -> str:
        drugs = report.get("patient", {}).get("drug", []) or []
        for drug in drugs:
            name = str(drug.get("medicinalproduct", "")).lower()
            if drug_name.lower() in name:
                dose = drug.get("drugdosagetext") or drug.get("drugdosage")
                return str(dose) if dose else "unspecified dose"
        return "unspecified dose"
