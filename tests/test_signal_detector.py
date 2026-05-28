import pytest

from pipeline.signal_detector import SignalDetector


def test_prr_basic():
    detector = SignalDetector()
    result = detector.calculate_prr(a=10, b=90, c=5, d=895)
    assert result["prr"] == pytest.approx(18.0, abs=0.5)


def test_prr_no_signal():
    detector = SignalDetector()
    result = detector.calculate_prr(a=2, b=98, c=2, d=898)
    chi2 = detector.calculate_chi2(a=2, b=98, c=2, d=898)
    assert detector.is_signal(a=2, prr=result["prr"], chi2=chi2) is False


def test_prr_division_by_zero():
    detector = SignalDetector()
    result = detector.calculate_prr(a=0, b=0, c=5, d=995)
    assert result == {"prr": None, "prr_lower": None, "prr_upper": None}


def test_ror_basic():
    detector = SignalDetector()
    result = detector.calculate_ror(a=10, b=90, c=5, d=895)
    assert result["ror"] > 1.0


def test_chi2_basic():
    detector = SignalDetector()
    assert detector.calculate_chi2(a=10, b=90, c=5, d=895) > 0


def test_is_signal_all_criteria_met():
    detector = SignalDetector()
    assert detector.is_signal(a=10, prr=3.0, chi2=6.0) is True


def test_is_signal_fails_prr():
    detector = SignalDetector()
    assert detector.is_signal(a=10, prr=1.5, chi2=6.0) is False


def test_background_estimate_not_inflated():
    """PRR should not be inflated by the old 0.1 background multiplier bug."""
    import pandas as pd

    detector = SignalDetector()
    df = pd.DataFrame(
        {
            "event_pt": ["Nausea"] * 100 + ["Headache"] * 50 + ["Rash"] * 10,
            "primaryid": range(160),
        }
    )
    signals = detector.analyze_drug(df, total_db_count=20_000_000)
    assert signals is not None
    assert not signals.empty
    assert signals["prr"].dropna().max() < 2.0
