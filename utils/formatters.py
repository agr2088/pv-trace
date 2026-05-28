"""Output formatting helpers for the Streamlit interface."""

from datetime import datetime

import pandas as pd

from config.settings import DATE_INPUT_FORMATS, DISPLAY_DATE_FORMAT


class OutputFormatter:
    """Format PV-Trace values for display and export."""

    def format_prr(self, prr: float, lower: float, upper: float) -> str:
        if prr is None or lower is None or upper is None or pd.isna(prr) or pd.isna(lower) or pd.isna(upper):
            return "N/A"
        return f"{prr:.2f} (95% CI: {lower:.2f} - {upper:.2f})"

    def format_signal_badge(self, is_signal: bool) -> str:
        if bool(is_signal):
            return "🔴 SIGNAL"
        return "🟡 MONITOR"

    def format_deadline_status(self, status: str) -> str:
        return status if status in {"OVERDUE", "DUE SOON", "ON TRACK"} else str(status)

    def format_date(self, date_str: str) -> str:
        for fmt in DATE_INPUT_FORMATS:
            try:
                return datetime.strptime(str(date_str), fmt).strftime(DISPLAY_DATE_FORMAT)
            except ValueError:
                continue
        return str(date_str)

    def dataframe_to_display(self, df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
        if df.empty:
            return pd.DataFrame(columns=columns)
        available_columns = [column for column in columns if column in df.columns]
        return df.loc[:, available_columns].fillna("N/A")
