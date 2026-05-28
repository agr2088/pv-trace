def test_parse_multi_reaction_returns_multiple_rows():
    from pipeline.ingestor import OpenFDAIngestor

    ingestor = OpenFDAIngestor()
    report = {
        "primaryid": "12345",
        "receivedate": "20240101",
        "serious": "1",
        "seriousnesshospitalization": "1",
        "patient": {
            "reaction": [
                {"reactionmeddrapt": "Nausea"},
                {"reactionmeddrapt": "Renal failure"},
            ],
            "drug": [],
        },
    }
    rows = ingestor._parse_report_all_reactions(report, "TestDrug")
    assert len(rows) == 2
    events = {row["event_pt"] for row in rows}
    assert "Nausea" in events
    assert "Renal failure" in events
    assert all(row["primaryid"] == "12345" for row in rows)


def test_narrative_case_id_not_empty():
    import pandas as pd

    from pipeline.narrative_writer import NarrativeWriter

    df = pd.DataFrame(
        [
            {
                "primaryid": "ABC123",
                "drug_name": "TestDrug",
                "event_pt": "Rash",
                "outcome_code": "HO",
                "outcome_label": "Hospitalisation",
                "receive_date": "20240101",
                "reporter_country": "US",
                "serious": True,
                "age": "45-yr-old",
                "gender": "male",
                "dose": "10mg",
            }
        ]
    )
    writer = NarrativeWriter()
    narratives = writer.generate_batch(df)
    assert narratives[0]["case_id"] == "ABC123"
