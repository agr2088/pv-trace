import pytest

from pipeline.signal_detector import SignalDetector


def test_prr_basic():
    detector = SignalDetector()
    result = detector.calculate_prr(a=10, b=90, c=5, d=895)
    assert result["prr"] == pytest.approx(18.0, abs=0.5)


def test_prr_no_signal():
    detector = SignalDetector()
    result = detector.calculate_prr(a=2, b=98, c=2, d=898)
    ror_result = detector.calculate_ror(a=2, b=98, c=2, d=898)
    chi2 = detector.calculate_chi2(a=2, b=98, c=2, d=898)
    assert detector.is_signal(a=2, prr=result["prr"], ror=ror_result["ror"], chi2=chi2) is False


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
    ror = detector.calculate_ror(a=10, b=90, c=5, d=895)["ror"]
    assert detector.is_signal(a=10, prr=3.0, ror=ror, chi2=6.0) is True


def test_is_signal_fails_prr():
    detector = SignalDetector()
    ror = detector.calculate_ror(a=10, b=90, c=5, d=895)["ror"]
    assert detector.is_signal(a=10, prr=1.5, ror=ror, chi2=6.0) is False


def test_is_signal_fails_ror():
    """is_signal should reject when ROR is below threshold even if PRR and chi2 pass."""
    detector = SignalDetector()
    assert detector.is_signal(a=10, prr=3.0, ror=1.0, chi2=6.0) is False


def test_missing_background_uses_conservative_population_rate():
    """Missing background counts should use the configured 1-per-10,000 estimate."""
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
    nausea = signals.loc[signals["event_pt"] == "Nausea"].iloc[0]
    assert nausea["prr"] == pytest.approx(6253.0, rel=0.01)


def test_dedup_by_primaryid_before_counting():
    """Case counts must be unique cases, not reaction-exploded rows."""
    import pandas as pd

    detector = SignalDetector()
    rows = []
    for pid in range(1, 6):
        rows.append({"primaryid": str(pid), "event_pt": "Nausea"})
    for pid in range(6, 9):
        rows.append({"primaryid": str(pid), "event_pt": "Nausea"})
        rows.append({"primaryid": str(pid), "event_pt": "Headache"})
    df = pd.DataFrame(rows)
    signals = detector.analyze_drug(df, total_db_count=10_000_000)
    nausea = signals.loc[signals["event_pt"] == "Nausea"].iloc[0]
    headache = signals.loc[signals["event_pt"] == "Headache"].iloc[0]
    assert int(nausea["case_count"]) == 8
    assert int(headache["case_count"]) == 3
