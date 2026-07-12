"""Tests for E2B(R3) XML export."""
from pipeline.e2b_exporter import E2BExporter


def test_export_case_contains_xml_declaration():
    exporter = E2BExporter()
    case = {
        "primaryid": "TEST-001",
        "drug_name": "TestDrug",
        "event_pt": "Rash",
        "outcome_code": "HO",
        "reaction_outcome": "3",
        "receive_date": "20240101",
        "reporter_country": "US",
        "serious": True,
        "age": "45-yr-old",
        "gender": "male",
        "dose": "10mg",
        "narrative": "Test narrative.",
    }
    xml = exporter.export_case(case)
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')


def test_export_case_reactionoutcome_from_real_field():
    """reactionoutcome must come from reaction_outcome, not outcome_code."""
    exporter = E2BExporter()
    case = {
        "primaryid": "TEST-002",
        "drug_name": "TestDrug",
        "event_pt": "Headache",
        "outcome_code": "DE",
        "reaction_outcome": "5",
        "receive_date": "20240101",
        "reporter_country": "US",
        "serious": True,
        "age": "30-yr-old",
        "gender": "female",
        "dose": "5mg",
        "narrative": "",
    }
    xml = exporter.export_case(case)
    assert "<reactionoutcome>5</reactionoutcome>" in xml
    assert "<reactionoutcome>DE</reactionoutcome>" not in xml


def test_export_case_defaults_to_unknown_when_reactionoutcome_empty():
    """Missing reaction_outcome should default to '6' (unknown)."""
    exporter = E2BExporter()
    case = {
        "primaryid": "TEST-003",
        "drug_name": "TestDrug",
        "event_pt": "Nausea",
        "outcome_code": "OT",
        "reaction_outcome": "",
        "receive_date": "20240101",
        "reporter_country": "US",
        "serious": False,
        "age": "unknown age",
        "gender": "patient",
        "dose": "unspecified dose",
        "narrative": "",
    }
    xml = exporter.export_case(case)
    assert "<reactionoutcome>6</reactionoutcome>" in xml


def test_export_batch_respects_limit():
    exporter = E2BExporter()
    cases = [
        {"primaryid": f"C-{i}", "drug_name": "X", "event_pt": "Y", "reaction_outcome": "6", "narrative": ""}
        for i in range(10)
    ]
    exports = exporter.export_batch(cases)
    assert len(exports) == 5
