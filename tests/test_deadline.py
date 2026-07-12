from datetime import date, timedelta

from pipeline.deadline_calculator import DeadlineCalculator


def test_death_deadline_uses_seven_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("DE", True) == 7


def test_serious_deadline_uses_fifteen_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("HO", True) == 15


def test_life_threatening_deadline_uses_seven_day_rule():
    """ICH E2A §3.2: life-threatening unexpected reactions -> 7-day expedited reporting."""
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("LT", True) == 7, (
        "Life-threatening cases must use the 7-day ICH E2A rule, not the 15-day serious rule."
    )


def test_congenital_anomaly_uses_fifteen_day_rule():
    """ICH E2A §3.3: congenital anomaly -> 15-day serious unexpected reporting."""
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("CA", True) == 15


def test_non_serious_deadline_uses_ninety_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("OT", False) == 90


def test_calculate_deadline_parses_yyyymmdd():
    calculator = DeadlineCalculator()
    received = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    result = calculator.calculate_deadline(received, "DE", True)
    assert result["deadline_days"] == 7
    assert result["rule_reference"] == "ICH E2A §3.2 - Fatal/Life-threatening (7-day rule) *(assumes unexpected)*"


def test_regional_life_threatening_rules_differentiate_cdsco():
    calculator = DeadlineCalculator()
    rows = calculator.get_regional_deadlines("LT", True)
    by_region = {row["Region"]: row for row in rows}
    assert by_region["FDA (USA)"]["Deadline (days)"] == 7
    assert by_region["EMA (Europe)"]["Deadline (days)"] == 7
    assert by_region["WHO-UMC"]["Deadline (days)"] == 7
    assert by_region["CDSCO (India)"]["Deadline (days)"] == 15


def test_ri_outcome_uses_fifteen_day_rule():
    """RI is serious but not fatal/LT, so should use 15-day rule."""
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("RI", True) == 15


def test_ot_outcome_serious_uses_fifteen_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("OT", True) == 15


def test_deadline_rule_reference_includes_assumes_unexpected():
    calculator = DeadlineCalculator()
    ref = calculator._rule_reference(7)
    assert "assumes unexpected" in ref
    ref15 = calculator._rule_reference(15)
    assert "assumes unexpected" in ref15
    ref90 = calculator._rule_reference(90)
    assert "assumes unexpected" not in ref90
