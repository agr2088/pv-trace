"""ICH E2A deadline calculation."""

from datetime import date, datetime, timedelta

import pandas as pd

from config.settings import (
    DATE_INPUT_FORMATS,
    FATAL_UNEXPECTED_DAYS,
    ISO_DATE_FORMAT,
    NON_SERIOUS_DAYS,
    REGIONS,
    SERIOUS_UNEXPECTED_DAYS,
)


class DeadlineCalculator:
    """Assign reporting deadlines using ICH E2A 7/15/90-day rules."""

    def __init__(self):
        self.fatal_days = FATAL_UNEXPECTED_DAYS
        self.serious_days = SERIOUS_UNEXPECTED_DAYS
        self.non_serious_days = NON_SERIOUS_DAYS

    def get_deadline_days(self, outcome_code: str, serious: bool) -> int:
        """Return ICH E2A reporting deadline days.

        Fatal (DE) and life-threatening (LT) unexpected -> 7 days (ICH E2A §3.2)
        Other serious unexpected (HO, DS, CA, OT) -> 15 days (ICH E2A §3.3)
        Non-serious -> 90 days (ICH E2A §3.4)
        """
        from config.settings import FATAL_OUTCOME_CODES, LIFE_THREATENING_CODES

        if outcome_code in FATAL_OUTCOME_CODES or outcome_code in LIFE_THREATENING_CODES:
            return self.fatal_days
        if serious:
            return self.serious_days
        return self.non_serious_days

    def calculate_deadline(self, receive_date: str, outcome_code: str, serious: bool) -> dict:
        parsed_date = self._parse_date(receive_date)
        deadline_days = self.get_deadline_days(outcome_code, serious)
        deadline_date = parsed_date + timedelta(days=deadline_days)
        days_remaining = (deadline_date - date.today()).days
        if days_remaining < 0:
            status = "OVERDUE"
        elif days_remaining <= 3:
            status = "DUE SOON"
        else:
            status = "ON TRACK"
        return {
            "deadline_days": deadline_days,
            "deadline_date": deadline_date.strftime(ISO_DATE_FORMAT),
            "days_remaining": days_remaining,
            "deadline_status": status,
            "rule_reference": self._rule_reference(deadline_days),
        }

    def calculate_batch(self, df: pd.DataFrame) -> pd.DataFrame:
        output = df.copy()
        if output.empty:
            return output
        deadline_rows = output.apply(
            lambda row: self.calculate_deadline(
                row.get("receive_date", ""),
                row.get("outcome_code", ""),
                bool(row.get("serious", False)),
            ),
            axis=1,
        )
        deadline_df = pd.DataFrame(deadline_rows.tolist())
        return pd.concat([output.reset_index(drop=True), deadline_df.reset_index(drop=True)], axis=1)

    def get_regional_deadlines(self, outcome_code: str, serious: bool) -> list[dict]:
        """
        Return real regional reporting deadlines for each authority.
        All rules come from config.settings.REGIONAL_DEADLINE_RULES.
        """
        from config.settings import (
            FATAL_OUTCOME_CODES,
            LIFE_THREATENING_CODES,
            REGIONAL_DEADLINE_RULES,
        )

        results = []
        for region, rules in REGIONAL_DEADLINE_RULES.items():
            if outcome_code in FATAL_OUTCOME_CODES:
                days = rules["fatal_days"]
                category = "Fatal"
            elif outcome_code in LIFE_THREATENING_CODES:
                days = rules["life_threatening_days"]
                category = "Life-threatening"
            elif serious:
                days = rules["serious_days"]
                category = "Serious unexpected"
            else:
                days = rules["non_serious_days"]
                category = "Non-serious"

            results.append(
                {
                    "Region": region,
                    "Category": category,
                    "Deadline (days)": days,
                    "Rule Reference": rules["reference"],
                }
            )

        return results

    @staticmethod
    def _parse_date(date_str: str) -> date:
        for fmt in DATE_INPUT_FORMATS:
            try:
                return datetime.strptime(str(date_str), fmt).date()
            except ValueError:
                continue
        return date.today()

    @staticmethod
    def _rule_reference(deadline_days: int) -> str:
        references = {
            7: "ICH E2A §3.2 - Fatal/Life-threatening (7-day rule)",
            15: "ICH E2A §3.3 - Serious unexpected (15-day rule)",
            90: "ICH E2A §3.4 - Non-serious (90-day rule)",
        }
        return references.get(deadline_days, f"ICH E2A - {deadline_days}-day rule")
