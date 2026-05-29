"""Input validation helpers."""

import re
from datetime import datetime

from config.settings import DATE_INPUT_FORMATS


class InputValidator:
    """Validate and sanitize user-provided query values."""

    def validate_drug_name(self, drug_name: str) -> tuple[bool, str]:
        if drug_name is None or not str(drug_name).strip():
            return False, "Drug name is required"
        cleaned = str(drug_name).strip()
        if len(cleaned) < 2:
            return False, "Drug name must be at least 2 characters"
        if len(cleaned) > 100:
            return False, "Drug name must be 100 characters or fewer"
        if not re.fullmatch(r"[A-Za-z0-9\s\-\.]+", cleaned):
            return False, "Drug name may contain only letters, numbers, spaces, hyphens, and dots"
        return True, ""

    def validate_date(self, date_str: str) -> tuple[bool, str]:
        for fmt in DATE_INPUT_FORMATS:
            try:
                datetime.strptime(str(date_str), fmt)
                return True, ""
            except ValueError:
                continue
        return False, "Invalid date format"

    def sanitize_drug_name(self, drug_name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9\s-]", "", str(drug_name or "").strip())
        return re.sub(r"\s+", " ", cleaned).title()
