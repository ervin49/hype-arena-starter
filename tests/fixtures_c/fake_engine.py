"""A stand-in for A's engine, with the contract v1 signatures. Tests and demo mode only.

Its verdicts are synthetic: they say nothing about Hooly.
"""
from types import SimpleNamespace


def build_kb(practice_rows, lexicon):
    return {"rows": len(practice_rows)}


def check_fact(fact, at_date, kb, exclude_row_ids=()):
    return {"status": "unknown", "confidence": None, "evidence_ids": [], "reason": "Synthetic fixture."}


def build_extractor(practice_rows, lexicon):
    return {}


def extract(row, lexicon, extractor):
    return {"facts": [], "complete": False, "issues": ["Synthetic fixture"]}


def classify(row, extraction, check):
    # Deterministic and fake: ids ending in an even digit are "true", the rest unsure.
    if row["id"][-1:] in "02468":
        return {"id": row["id"], "label": "true", "confidence": 0.75, "evidence_ids": [],
                "reason": "Synthetic fixture."}
    return {"id": row["id"], "label": "unsure", "confidence": None, "evidence_ids": [],
            "reason": "Synthetic fixture; real verifier not connected."}


ENGINE = SimpleNamespace(build_kb=build_kb, check_fact=check_fact, build_extractor=build_extractor,
                         extract=extract, classify=classify)
