import json
import os
import subprocess
import sys
from collections import Counter

import pytest

from arena import runner
from arena.generate import MAX_CLAIMS_PER_EVENT, MAX_CLAIMS_PER_FACT, MAX_DATE_COMPARES_PER_FACT, select_claims
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
    per_fact, date_compared, per_event = Counter(), set(), Counter()
    for c in claims:
        f = c["form"]
        if c["type"] == "compare":
            for side in (f["left"], f["right"]):
                per_fact[(side["subject"], side["attribute"])] += 1
                if c["group"] == "compare.date":
                    date_compared.add((side["subject"], side["attribute"]))
        elif c["type"] != "relation":
            per_fact[(f["subject"], f["attribute"])] += 1
        if c["type"] == "at_event":
            per_event[f["event"]] += 1
    for fact, n in per_fact.items():
        assert n <= (MAX_DATE_COMPARES_PER_FACT if fact in date_compared else MAX_CLAIMS_PER_FACT * 3), fact
    assert max(per_event.values()) <= MAX_CLAIMS_PER_EVENT


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


def test_confidence_comes_from_the_backtest(selected):
    from arena.generate import load_calibration
    table = load_calibration()
    assert table, "reports/claims_calibration.json is missing: run scripts/backtest_claims.py"
    claims, _ = selected
    for c in claims:
        assert table[c["group"]]["keep"] and c["confidence"] == table[c["group"]]["confidence"], c


def test_groups_that_go_stale_are_dropped():
    from arena.generate import load_calibration
    table = load_calibration()
    assert not table["fact.unchanged"]["keep"] and not table["fact.changed"]["keep"]


def test_a_reserve_of_at_least_150():
    pool, _ = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 5000)
    assert len(pool) >= 1150


def test_calibration_rules():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bt", os.path.join(ROOT, "scripts", "backtest_claims.py"))
    bt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt)
    assert bt.wilson_lower(0, 0) == 0.0 and 0.98 < bt.wilson_lower(400, 400) < 0.991
    cut = {c: {} for c in bt.CUTOFFS}
    cut[bt.CUTOFFS[0]] = {"good": {"right": 100, "wrong": 0, "unknown": 3}, "bad": {"right": 90, "wrong": 10, "unknown": 0},
                         "rare": {"right": 3, "wrong": 0, "unknown": 0}}
    groups = {g["group"]: g for g in bt.calibration(cut)}
    assert groups["good"]["keep"] and groups["good"]["confidence"] <= 1.0
    assert not groups["bad"]["keep"]
    assert groups["rare"]["keep"] and groups["rare"]["confidence"] == bt.UNMEASURED_CONFIDENCE
    assert groups["good"]["confidence"] <= bt.UNVERIFIED_CAP  # no strict judge: capped


def test_the_strict_judge_lowers_or_drops():
    import importlib.util
    spec = importlib.util.spec_from_file_location("bt", os.path.join(ROOT, "scripts", "backtest_claims.py"))
    bt = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bt)
    full = {c: {} for c in bt.CUTOFFS}
    full[bt.CUTOFFS[0]] = {"checked": {"right": 400, "wrong": 0, "unknown": 0}, "refuted": {"right": 400, "wrong": 0, "unknown": 0}}
    strict = {c: {} for c in bt.CUTOFFS}
    strict[bt.CUTOFFS[0]] = {"checked": {"right": 50, "wrong": 0, "unknown": 350}, "refuted": {"right": 40, "wrong": 10, "unknown": 350}}
    groups = {g["group"]: g for g in bt.calibration(full, strict)}
    assert groups["checked"]["keep"] and groups["checked"]["confidence"] == round(bt.wilson_lower(50, 50), 3)
    assert not groups["refuted"]["keep"]


def test_shipped_confidence_is_never_above_the_strict_evidence():
    from arena.generate import load_calibration
    for g in load_calibration().values():
        if g["keep"] and g["n"] >= 20:
            assert g["confidence"] <= (0.99 if g["strict_n"] >= 20 else 0.95), g


def test_wording_reads_like_english():
    from arena.generate import _had, possessive
    assert possessive("Hooly Docs") == "Hooly Docs'" and possessive("Hooly") == "Hooly's"
    assert _had("employees", "38 employees") == "38 employees"
    assert _had("monthly_active_users", "341,000,000 users") == "341,000,000 monthly active users"
    assert _had("official_sdks", "5 sdks") == "5 official SDKs"
    assert _had("languages_served", "71 languages") is None  # the noun is not the attribute's last word
    assert _had("price", "€59 per month") is None
