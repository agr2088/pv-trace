from datetime import date, timedelta

from pipeline.deadline_calculator import DeadlineCalculator


def test_death_deadline_uses_seven_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("DE", True) == 7


def test_serious_deadline_uses_fifteen_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("HO", True) == 15


def test_non_serious_deadline_uses_ninety_day_rule():
    calculator = DeadlineCalculator()
    assert calculator.get_deadline_days("OT", False) == 90


def test_calculate_deadline_parses_yyyymmdd():
    calculator = DeadlineCalculator()
    received = (date.today() - timedelta(days=1)).strftime("%Y%m%d")
    result = calculator.calculate_deadline(received, "DE", True)
    assert result["deadline_days"] == 7
    assert result["rule_reference"] == "ICH E2A - 7-day rule"


def test_regional_life_threatening_rules_differentiate_cdsco():
    calculator = DeadlineCalculator()
    rows = calculator.get_regional_deadlines("LT", True)
    by_region = {row["Region"]: row for row in rows}
    assert by_region["FDA (USA)"]["Deadline (days)"] == 7
    assert by_region["EMA (Europe)"]["Deadline (days)"] == 7
    assert by_region["WHO-UMC"]["Deadline (days)"] == 7
    assert by_region["CDSCO (India)"]["Deadline (days)"] == 15
