import json
import os
import types

from arena import controls, runner
from arena.generate import select_claims
from arena.io import read_lexicon, read_rows
from tests.fixtures_c.fake_engine import ENGINE
from tests.test_runner import read_output, universe  # noqa: F401  (the fixture)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRACTICE_PATH = os.path.join(ROOT, "data", "practice.csv")
PRACTICE = read_rows(PRACTICE_PATH, require_form=True)
LEXICON = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
TEXTS = [r["text"] for r in PRACTICE]


def test_over_stated_confidence_is_lowered():
    answers = [(0.95, 1.0)] * 60 + [(0.95, 0.0)] * 40  # says 0.95, right 60%
    k = controls.fit_factor(answers)
    assert k < 1 and abs(controls.shrink(0.95, k) - 0.6) < 0.03


def test_honest_or_modest_confidence_is_kept():
    assert controls.fit_factor([(0.8, 1.0)] * 90 + [(0.8, 0.0)] * 10) == 1.0  # says 0.8, right 90%: never raised


def test_too_small_a_control_group_changes_nothing():
    factors, report = controls.measure([{"id": "a", "label": "true", "confidence": 0.99}], {"a": "false"})
    assert factors == {"true": 1.0, "false": 1.0} and "too few" in report["note"]


def test_apply_lowers_within_the_range_and_skips_unsure():
    preds = {"a": {"label": "true", "confidence": 0.9}, "b": {"label": "unsure", "confidence": None},
             "c": {"label": "false", "confidence": 0.7}}
    controls.apply(preds, {"true": 0.5, "false": 0.0})
    assert preds["a"]["confidence"] == 0.7 and preds["b"]["confidence"] is None and preds["c"]["confidence"] == 0.5


def test_the_control_group_is_hidden_from_the_engine():
    rows = [{"id": "p-1", "label": "true"}, {"id": "p-2", "label": "false"}, {"id": "u-1", "label": ""}]
    hidden, practice, group, _ = controls.control_input(rows, [{"id": "p-1"}, {"id": "p-2"}], {"p-2"})
    assert [r["label"] for r in hidden] == ["true", "", ""] and practice == [{"id": "p-1"}] and group == ["p-2"]


def test_the_shipped_control_model_never_saw_its_group():
    ids, m1, m2 = controls.load_control()
    with open(os.path.join(controls.CONTROL_DIR, "ids.json"), encoding="utf-8") as f:
        meta = json.load(f)["meta"]
    assert m1 and m2 and len(ids) == meta["control_rows"] > 300
    assert meta["trained_on"].endswith(f"{len(PRACTICE) - len(ids)} rows")


def test_a_confident_row_that_contradicts_a_claim_vetoes_it():
    claims, _ = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 1000)
    target = next(c for c in claims if c["group"] == "compare.date")
    left = target["form"]["left"]
    wrong = {"id": "u-1", "text": "x", "date": "2026-10-20", "label": "true",
             "form": json.dumps([{"subject": left["subject"], "attribute": left["attribute"],
                                  "value": {"kind": "date", "value": "2026-10-01"}}])}
    again, report = select_claims(PRACTICE, LEXICON, "2026-10-29", TEXTS, 1000, check_rows=[wrong])
    assert report["vetoed_by_input"] > 0 and len(again) == 1000
    assert target["form"] not in [c["form"] for c in again]


def test_check_rows_keeps_only_confident_complete_true_rows():
    rows = [{"id": i, "text": "t", "date": "2026-01-01", "label": ""} for i in "abcd"]
    ex = {"complete": True, "facts": [{"subject": "Hooly", "attribute": "ceo", "value": {"kind": "name", "value": "X"}}]}
    batch = [{"id": "a", "label": "true", "confidence": 0.95, "extraction": ex},
             {"id": "b", "label": "true", "confidence": 0.6, "extraction": ex},
             {"id": "c", "label": "false", "confidence": 0.95, "extraction": ex},
             {"id": "d", "label": "true", "confidence": 0.95, "extraction": {**ex, "complete": False}}]
    assert [r["id"] for r in controls.check_rows(rows, batch)] == ["a"]


def test_the_run_lowers_an_over_confident_engine(universe):  # noqa: F811
    def label_rows(rows, practice, lexicon, kb=None, extractor=None, models=None):
        return [{"id": r["id"], "label": "true", "confidence": 0.99} for r in rows if not r["label"]]

    engine = types.SimpleNamespace(**{**vars(ENGINE), "label_rows": label_rows})
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE_PATH, engine=engine) == 0
    rows = [r for r in read_output(universe) if not r["type"]]
    assert {r["label"] for r in rows} == {"true"}
    assert all(float(r["confidence"]) < 0.95 for r in rows)  # always "true" is right ~85% of the time
