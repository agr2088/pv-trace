"""Signal detection calculations for adverse event disproportionality analysis."""

import math

import pandas as pd
from scipy.stats import chi2_contingency

from config.settings import CHI2_THRESHOLD, MIN_CASE_COUNT, PRR_THRESHOLD, ROR_THRESHOLD


class SignalDetector:
    """Calculate PRR, ROR, chi-square, and Evans criteria signal status."""

    def __init__(self):
        self.prr_threshold = PRR_THRESHOLD
        self.ror_threshold = ROR_THRESHOLD
        self.chi2_threshold = CHI2_THRESHOLD
        self.min_case_count = MIN_CASE_COUNT

    def calculate_prr(self, a: int, b: int, c: int, d: int) -> dict:
        """Calculate PRR and 95% CI used in WHO-UMC/Evans signal review."""
        try:
            if a <= 0 or c <= 0 or (a + b) <= 0 or (c + d) <= 0:
                raise ZeroDivisionError
            prr = (a / (a + b)) / (c / (c + d))
            standard_error = math.sqrt(1 / a - 1 / (a + b) + 1 / c - 1 / (c + d))
            return {
                "prr": prr,
                "prr_lower": math.exp(math.log(prr) - 1.96 * standard_error),
                "prr_upper": math.exp(math.log(prr) + 1.96 * standard_error),
            }
        except (ZeroDivisionError, ValueError):
            return {"prr": None, "prr_lower": None, "prr_upper": None}

    def calculate_ror(self, a: int, b: int, c: int, d: int) -> dict:
        """Calculate ROR and 95% CI for disproportionality screening."""
        try:
            if min(a, b, c, d) <= 0:
                raise ZeroDivisionError
            ror = (a * d) / (b * c)
            standard_error = math.sqrt(1 / a + 1 / b + 1 / c + 1 / d)
            return {
                "ror": ror,
                "ror_lower": math.exp(math.log(ror) - 1.96 * standard_error),
                "ror_upper": math.exp(math.log(ror) + 1.96 * standard_error),
            }
        except (ZeroDivisionError, ValueError):
            return {"ror": None, "ror_lower": None, "ror_upper": None}

    def calculate_chi2(self, a: int, b: int, c: int, d: int) -> float:
        if min(a, b, c, d) <= 0:
            return 0.0
        try:
            contingency = [[a, b], [c, d]]
            chi2, _, _, _ = chi2_contingency(contingency, correction=False)
            return float(chi2)
        except Exception:
            return 0.0

    def calculate_ebgm(self, a: int, b: int, c: int, d: int) -> float | None:
        """Calculate a simple empirical Bayes geometric mean shrinkage estimate."""
        total = a + b + c + d
        if total <= 0 or (a + b) <= 0 or (a + c) <= 0:
            return None
        expected = ((a + b) * (a + c)) / total
        return float((a + 0.5) / (expected + 0.5)) if expected > 0 else None

    def is_signal(self, a: int, prr: float, ror: float, chi2: float) -> bool:
        return bool(
            a >= self.min_case_count
            and prr is not None
            and prr >= self.prr_threshold
            and ror is not None
            and ror >= self.ror_threshold
            and chi2 >= self.chi2_threshold
        )

    def analyze_drug(
        self,
        drug_events_df: pd.DataFrame,
        total_db_count: int,
        event_background_counts: dict = None,
    ) -> pd.DataFrame:
        """
        Analyze drug-event pairs using WHO-UMC/Evans disproportionality criteria.

        Parameters
        ----------
        drug_events_df : DataFrame of FAERS cases for the drug
        total_db_count : total reports in FAERS database
        event_background_counts : optional dict of {event_pt: total_faers_count_for_event}
                                  If provided, uses real background counts.
                                  If None, estimates background from sample proportions.
        """
        columns = [
            "event_pt",
            "case_count",
            "prr",
            "prr_lower",
            "prr_upper",
            "ror",
            "ror_lower",
            "ror_upper",
            "ebgm",
            "chi2",
            "is_signal",
        ]
        if drug_events_df.empty:
            return pd.DataFrame(columns=columns)

        total_drug_cases = drug_events_df["primaryid"].nunique()
        background_total = max(int(total_db_count), total_drug_cases + 1)
        rows = []
        filled = drug_events_df["event_pt"].fillna("Unspecified adverse event")
        event_counts = drug_events_df.assign(event_pt=filled).groupby("event_pt")["primaryid"].nunique()

        for event_pt, a in event_counts.items():
            a = int(a)
            b = max(total_drug_cases - a, 0)

            if event_background_counts and event_pt in event_background_counts:
                total_event_in_db = int(event_background_counts[event_pt])
                c = max(total_event_in_db - a, 1)
            else:
                # Estimate background using a conservative population rate.
                # Assume background event rate = 1 per 10,000 FAERS reports
                # when real counts are unavailable.
                background_n = max(background_total - total_drug_cases, 1)
                c = max(int(background_n // 10_000), 1)

            d = max(background_total - a - b - c, 0)
            prr_result = self.calculate_prr(a, b, c, d)
            ror_result = self.calculate_ror(a, b, c, d)
            ebgm = self.calculate_ebgm(a, b, c, d)
            chi2 = self.calculate_chi2(a, b, c, d)
            rows.append(
                {
                    "event_pt": event_pt,
                    "case_count": a,
                    **prr_result,
                    **ror_result,
                    "ebgm": ebgm,
                    "chi2": chi2,
                    "is_signal": self.is_signal(a, prr_result["prr"], ror_result["ror"], chi2),
                }
            )

        return pd.DataFrame(rows, columns=columns).sort_values(
            by="prr", ascending=False, na_position="last"
        )
