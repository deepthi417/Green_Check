"""
GreenCheck scoring engine — the exact logic you tested by hand on the
Greenarys seed pencil claim, now organized as a reusable module with a
fuller keyword vocabulary and the risk-band classifier added on top.

Framework recap:
  INTENSITY: how strong/absolute the claim language is
  VERIFICATION CONFIDENCE: how much real evidence backs it (certifications,
    specific checkable numbers)
  GREENWASH RISK = INTENSITY * (1 - VERIFICATION_CONFIDENCE / 100)
"""
import re
from dataclasses import dataclass
from typing import List

ABSOLUTE_TERMS = [
    "100%", "zero waste", "completely biodegradable", "fully recyclable",
    "carbon neutral", "carbon negative", "net zero", "totally sustainable",
    "entirely sustainable", "zero emissions", "plastic-free", "toxin-free",
    "chemical-free", "all natural", "all-natural", "fully compostable",
]

MODERATE_TERMS = [
    "sustainably sourced", "sustainable", "eco-friendly", "environmentally friendly",
    "planet-friendly", "responsibly made", "ethically made", "low-impact",
    "reduced waste", "recycled materials", "recycled paper", "recycled",
    "upcycled", "biodegradable", "compostable", "renewable", "cruelty-free",
    "conscious", "eco-conscious",
]

VAGUE_TERMS = [
    "eco-friendly", "green", "natural", "sustainable", "environmentally friendly",
    "planet-friendly", "conscious", "responsible", "clean", "pure",
    "kind to the earth", "eco-conscious", "guilt-free",
]

CERTIFICATIONS = [
    "gots", "global organic textile standard", "fair trade", "fairtrade",
    "b corp", "bcorp", "b-corp", "certified b corporation",
    "fsc", "forest stewardship council", "global recycled standard", "grs",
    "oeko-tex", "usda organic", "climate neutral certified", "1% for the planet",
    "leaping bunny", "peta-approved vegan", "rainforest alliance",
    "cradle to cradle", "energy star", "bluesign", "recycled claim standard",
    "rcs", "responsible down standard", "rds", "organic content standard",
]

SPECIFIC_EVIDENCE_PATTERNS = [
    r"\d+%\s+recycled", r"\d+%\s+organic", r"made from \d+", r"sourced from \d+",
    r"third[- ]party (?:tested|verified|certified)", r"independently (?:tested|verified)",
]


@dataclass
class ScoreResult:
    intensity_score: float
    verification_confidence: float
    greenwash_risk_score: float
    risk_band: str
    matched_certifications: List[str]
    matched_vague_terms: List[str]

    def as_dict(self) -> dict:
        return {
            "intensity_score": round(self.intensity_score, 2),
            "verification_confidence": round(self.verification_confidence, 2),
            "greenwash_risk_score": round(self.greenwash_risk_score, 2),
            "risk_band": self.risk_band,
            "matched_certifications": self.matched_certifications,
            "matched_vague_terms": self.matched_vague_terms,
        }


def _find_matches(text: str, terms: List[str]) -> List[str]:
    text_lower = text.lower()
    return [t for t in terms if t in text_lower]


def _find_regex_matches(text: str, patterns: List[str]) -> List[str]:
    text_lower = text.lower()
    return [p for p in patterns if re.search(p, text_lower)]


def score_intensity(text: str) -> float:
    if not text.strip():
        return 0.0
    absolute_hits = _find_matches(text, ABSOLUTE_TERMS)
    moderate_hits = _find_matches(text, MODERATE_TERMS)
    raw = len(absolute_hits) * 45 + len(moderate_hits) * 22
    return min(100.0, raw)


def score_verification_confidence(text: str) -> float:
    if not text.strip():
        return 0.0
    cert_hits = _find_matches(text, CERTIFICATIONS)
    evidence_hits = _find_regex_matches(text, SPECIFIC_EVIDENCE_PATTERNS)
    raw = len(cert_hits) * 45 + len(evidence_hits) * 20
    return min(100.0, raw)


def classify_risk_band(risk_score: float) -> str:
    if risk_score < 20:
        return "low"
    if risk_score < 45:
        return "moderate"
    if risk_score < 70:
        return "high"
    return "severe"


def score_claim(claim_text: str) -> ScoreResult:
    intensity = score_intensity(claim_text)
    verification = score_verification_confidence(claim_text)
    risk = intensity * (1 - verification / 100)
    band = classify_risk_band(risk)

    return ScoreResult(
        intensity_score=intensity,
        verification_confidence=verification,
        greenwash_risk_score=risk,
        risk_band=band,
        matched_certifications=_find_matches(claim_text, CERTIFICATIONS),
        matched_vague_terms=_find_matches(claim_text, VAGUE_TERMS),
    )


if __name__ == "__main__":
    sample = ("Handcrafted from recycled paper and wrapped in vibrant multicolor "
              "designs, this eco-friendly pencil brings joy to writing.")
    result = score_claim(sample)
    print(result.as_dict())
