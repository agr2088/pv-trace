"""Tests for clinical explainer."""
from unittest.mock import patch

from pipeline.explainer import ClinicalExplainer


def test_template_fallback_used_when_no_hf_token():
    explainer = ClinicalExplainer()
    with patch("pipeline.explainer.HF_TOKEN", ""):
        result = explainer.explain_signal("Ibuprofen", "Headache", 3.5, 10, True)
    assert "Headache" in result
    assert "Ibuprofen" in result
    assert "signal" in result.lower()


def test_template_fallback_for_non_signal():
    explainer = ClinicalExplainer()
    with patch("pipeline.explainer.HF_TOKEN", ""):
        result = explainer.explain_signal("Ibuprofen", "Headache", 1.5, 5, False)
    assert "monitoring" in result.lower()


def test_explain_batch_handles_empty_df():
    import pandas as pd
    explainer = ClinicalExplainer()
    df = pd.DataFrame(columns=["event_pt", "prr", "case_count", "is_signal"])
    result = explainer.explain_batch(df, "TestDrug")
    assert result.empty
    assert "explanation" in result.columns
