"""ICH E2B(R3)-style XML export."""

from datetime import datetime
from xml.etree import ElementTree as ET

from config.settings import E2B_BATCH_LIMIT


class E2BExporter:
    """Export individual cases to a simple E2B(R3)-compatible XML structure."""

    def export_case(self, case: dict) -> str:
        root = ET.Element("ichicsr", {"lang": "en"})
        header = ET.SubElement(root, "ichicsrmessageheader")
        ET.SubElement(header, "messagetype").text = "ichicsr"
        ET.SubElement(header, "messagedate").text = datetime.utcnow().strftime("%Y%m%d%H%M%S")
        ET.SubElement(header, "messageidentifier").text = str(case.get("primaryid", ""))

        report = ET.SubElement(root, "safetyreport")
        ET.SubElement(report, "safetyreportid").text = str(case.get("primaryid", ""))
        ET.SubElement(report, "primarysourcecountry").text = str(case.get("reporter_country", "Unknown"))
        ET.SubElement(report, "receivedate").text = str(case.get("receive_date", ""))
        ET.SubElement(report, "serious").text = "1" if bool(case.get("serious", False)) else "2"
        narrative_text = str(case.get("narrative", "")).strip()
        if narrative_text:
            ET.SubElement(report, "narrativeincludeclinical").text = narrative_text

        patient = ET.SubElement(report, "patient")
        age_raw = str(case.get("age", ""))
        if age_raw and age_raw != "unknown age":
            ET.SubElement(patient, "patientonsetage").text = age_raw
        gender = str(case.get("gender", ""))
        if gender in ("male", "female"):
            ET.SubElement(patient, "patientsex").text = "1" if gender == "male" else "2"

        drug = ET.SubElement(patient, "drug")
        ET.SubElement(drug, "medicinalproduct").text = str(case.get("drug_name", ""))
        dose = str(case.get("dose", ""))
        if dose and dose != "unspecified dose":
            ET.SubElement(drug, "drugdosagetext").text = dose
        reaction = ET.SubElement(patient, "reaction")
        ET.SubElement(reaction, "reactionmeddrapt").text = str(case.get("event_pt", ""))
        ET.SubElement(reaction, "reactionoutcome").text = str(case.get("outcome_code", ""))

        ET.indent(root, space="  ")
        xml_body = ET.tostring(root, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}'

    def export_batch(self, cases: list[dict]) -> list[dict]:
        exports = []
        for case in cases[:E2B_BATCH_LIMIT]:
            exports.append({"case_id": case.get("primaryid", ""), "xml": self.export_case(case)})
        return exports
