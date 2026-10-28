import json
import os
import subprocess
import sys
from collections import Counter

import pytest

from arena import runner
from arena.generate import select_claims
from arena.io import read_lexicon, read_rows
from arena.validate import Validator
from tests.fixtures_c.fake_engine import ENGINE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRACTICE = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
LEXICON = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
TEXTS = [r["text"] for r in PRACTICE]


@pytest.fixture(scope="module")
def selected():
    return select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 1000)


def test_exactly_one_thousand_with_every_type(selected):
    claims, report = selected
    assert len(claims) == 1000
    assert set(Counter(c["type"] for c in claims)) == {"fact", "compare", "change", "at_event", "relation"}


def test_every_claim_validates_again(selected):
    claims, _ = selected
    v = Validator(PRACTICE, LEXICON, TEXTS)
    bad = [(c["text"], r["issues"]) for c in claims for r in [v.validate(c)] if not r["valid"]]
    assert bad == []


def test_unique_and_in_range(selected):
    claims, _ = selected
    assert len({c["id"] for c in claims}) == 1000
    assert len({c["text"].lower() for c in claims}) == 1000
    assert len({json.dumps(c["form"], sort_keys=True) for c in claims}) == 1000
    assert all(0.5 <= c["confidence"] <= 1 and len(c["text"]) <= 300 and c["label"] == "true" for c in claims)
    assert all(c["evidence_ids"] for c in claims)


def test_no_fact_carries_too_many_claims(selected):
    claims, _ = selected
    per_fact = Counter()
    for c in claims:
        f = c["form"]
        if c["type"] == "compare":
            per_fact[(f["left"]["subject"], f["left"]["attribute"])] += 1
            per_fact[(f["right"]["subject"], f["right"]["attribute"])] += 1
        elif c["type"] != "relation":
            per_fact[(f["subject"], f["attribute"])] += 1
    assert max(per_fact.values()) <= 18


def test_deterministic():
    a, _ = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 50)
    b, _ = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 50)
    assert a == b


def test_an_input_row_equal_to_a_claim_pushes_it_out(selected):
    claims, _ = selected
    taken = claims[0]["text"]
    again, _ = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS + [taken.upper()], 1000)
    assert len(again) == 1000 and taken.lower() not in {c["text"].lower() for c in again}


def test_full_run_with_the_real_generator_passes_the_official_checker(tmp_path):
    (tmp_path / "universe").mkdir()
    (tmp_path / "output").mkdir()
    practice = os.path.join(ROOT, "data", "practice.csv")
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "input.py"), practice,
                    str(tmp_path / "universe" / "universe.csv")], check=True, capture_output=True)
    (tmp_path / "universe" / "lexicon.json").write_text(open(os.path.join(ROOT, "data", "lexicon.json")).read())
    assert runner.run(str(tmp_path / "universe"), str(tmp_path / "output"), practice, engine=ENGINE) == 0
    check = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_output.py"), str(tmp_path / "output"),
                            practice, str(tmp_path / "universe" / "universe.csv")], capture_output=True, text=True)
    assert "claims: 1000 new claims" in check.stdout and "the format checks pass" in check.stdout, check.stdout
