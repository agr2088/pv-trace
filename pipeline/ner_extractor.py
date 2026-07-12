"""spaCy NER-based drug/adverse event extractor with biomedical model fallback."""

from __future__ import annotations

import spacy

from config.settings import (
    AE_ENTITY_LABELS,
    DRUG_ENTITY_LABELS,
    FALLBACK_AE_ENTITY_LABELS,
    FALLBACK_DRUG_ENTITY_LABELS,
    SOC_KEYWORDS,
    SPACY_MODEL_FALLBACK,
    SPACY_MODEL_PRIMARY,
)


_NLP = None


def _get_nlp():
    global _NLP
    if _NLP is None:
        try:
            _NLP = spacy.load(SPACY_MODEL_PRIMARY)
        except OSError:
            try:
                _NLP = spacy.load(SPACY_MODEL_FALLBACK)
            except OSError as error:
                raise RuntimeError(
                    "No spaCy model found. Run: pip install scispacy && "
                    "pip install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/"
                    "v0.5.4/en_core_sci_sm-0.5.4.tar.gz"
                ) from error
    return _NLP


class NERExtractor:
    """Extract drug names, adverse event terms, and SOC classifications from clinical free text."""

    def __init__(self):
        self.nlp = _get_nlp()
        self._is_biomedical = hasattr(self.nlp, "meta") and (
            "scispacy" in str(self.nlp.meta.get("description", "")).lower()
            or self.nlp.meta.get("name", "").startswith("en_core_sci")
        )

    def extract_entities(self, text: str) -> dict:
        """Return extracted drugs, AE terms, SOC labels, and patient demographics."""
        doc = self.nlp(str(text))
        drugs = []
        ae_terms = []
        demographics = {}

        for ent in doc.ents:
            label = ent.label_
            value = ent.text.strip()
            if len(value) < 2:
                continue
            if self._is_biomedical:
                if label in DRUG_ENTITY_LABELS:
                    drugs.append(value)
                elif label in AE_ENTITY_LABELS:
                    ae_terms.append(value)
            else:
                if label in FALLBACK_DRUG_ENTITY_LABELS:
                    drugs.append(value)
                elif label in FALLBACK_AE_ENTITY_LABELS:
                    ae_terms.append(value)
            if label == "DATE":
                demographics.setdefault("dates", []).append(value)
            if label == "CARDINAL":
                context = doc[max(0, ent.start - 3) : ent.end + 3].text.lower()
                if any(word in context for word in ["year", "yr", "old", "age"]):
                    demographics["age"] = value

        text_lower = str(text).lower()
        soc_hits = []
        for soc, keywords in SOC_KEYWORDS.items():
            matched = [keyword for keyword in keywords if keyword in text_lower]
            if matched:
                soc_hits.append({"soc": soc, "matched_terms": matched})
                ae_terms.extend(matched)

        return {
            "drugs": list(dict.fromkeys(drugs)),
            "ae_terms": list(dict.fromkeys(ae_terms)),
            "soc_classifications": soc_hits,
            "demographics": demographics,
            "sentence_count": len(list(doc.sents)),
            "token_count": len(doc),
            "model_used": self.nlp.meta.get("name", "unknown"),
            "ae_extraction_mode": "NER" if self._is_biomedical else "SOC_KEYWORDS_ONLY",
        }

    def suggest_drug_query(self, text: str) -> str | None:
        """Try to extract the most likely drug name to use as a FAERS search term."""
        result = self.extract_entities(text)
        return result["drugs"][0] if result["drugs"] else None
