"""The claims the generator ships, and every candidate it could ship, pass the independent referee.

scripts/referee.py reads the spec without arena/validate.py; this runs it on what arena.generate
selects for the practice data, so a claims change the referee disagrees with fails here.
"""
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import referee as R  # noqa: E402

from arena.generate import select_claims  # noqa: E402
from arena.io import read_lexicon, read_rows  # noqa: E402

AS_OF = "2026-10-29"
PRACTICE = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
LEXICON = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
TEXTS = [r["text"] for r in PRACTICE]
REFEREE = R.Referee(R.Lexicon(json.load(open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8"))),
                    R.attribute_kinds(os.path.join(ROOT, "data", "practice.csv")))
VALIDATOR = R.schema_validator()


def rejections(claims):
    out = []
    for i, c in enumerate(claims):
        form = json.loads(c["form"]) if isinstance(c["form"], str) else c["form"]
        entry = {"id": c.get("id") or f"c{i}", "type": c["type"], "text": c["text"], "form": form,
                 "tag": "true", "confidence": c["confidence"]}
        errs = [e.message for e in VALIDATOR.iter_errors(entry)]
        errs += [f"{rule}: {detail}" for rule, detail in R.lexicon_rules(REFEREE.lex, c["type"], form)]
        if not errs:
            errs += [f"{rule}: {detail}" for rule, detail, _ in REFEREE.check(c["type"], form, c["text"])]
        if c["text"].strip() in TEXTS:
            errs.append("not new: the text is a practice row")
        if errs:
            out.append((c["text"], errs))
    return out


@pytest.fixture(scope="module")
def shipped():
    claims, _ = select_claims(PRACTICE, LEXICON, AS_OF, TEXTS, 1000)
    return claims


def test_exactly_1000_claims_all_accepted_by_the_referee(shipped):
    assert len(shipped) == 1000
    bad = rejections(shipped)
    assert not bad, f"{len(bad)} rejected, first: {bad[:3]}"


def test_every_reserve_candidate_is_accepted_too():
    pool, _ = select_claims(PRACTICE, LEXICON, AS_OF, TEXTS, 5000)
    bad = rejections(pool)
    assert not bad, f"{len(bad)} of {len(pool)} rejected, first: {bad[:3]}"
