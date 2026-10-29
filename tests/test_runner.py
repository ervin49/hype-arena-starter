import csv
import os
import shutil
import subprocess
import sys
import types

import pytest

from arena import runner
from tests.fixtures_c.fake_engine import ENGINE

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PRACTICE = os.path.join(ROOT, "data", "practice.csv")


def fake_claims(practice, lexicon, as_of, input_texts, n):
    claims = [{"id": f"t-{i}", "type": "fact", "text": f"Synthetic claim number {i}.",
               "form": {"subject": "Hooly", "attribute": "employees",
                        "value": {"kind": "quantity", "value": i, "unit": "employee"}},
               "label": "true", "confidence": 0.6} for i in range(n)]
    return claims, {"synthetic": n}


@pytest.fixture
def universe(tmp_path, monkeypatch):
    """The practice data in the run's shape, every fifth label hidden, as scripts/check.sh makes it."""
    monkeypatch.setitem(sys.modules, "arena.generate", types.SimpleNamespace(select_claims=fake_claims))
    (tmp_path / "universe").mkdir()
    (tmp_path / "output").mkdir()
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "input.py"), PRACTICE,
                    str(tmp_path / "universe" / "universe.csv")], check=True, capture_output=True)
    shutil.copy(os.path.join(ROOT, "data", "lexicon.json"), tmp_path / "universe")
    return tmp_path


def read_output(path):
    with open(path / "output" / "output.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def test_run_passes_the_official_checker(universe):
    status = runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE)
    assert status == 0
    rows = read_output(universe)
    labels = [r for r in rows if not r["type"]]
    assert len(labels) == 380  # 1,897 rows, every fifth hidden
    assert {r["label"] for r in labels} == {"true", "unsure"}
    assert sum(1 for r in rows if r["type"]) == 1000
    check = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_output.py"),
                            str(universe / "output"), PRACTICE, str(universe / "universe" / "universe.csv")],
                           capture_output=True, text=True)
    assert "the format checks pass" in check.stdout, check.stdout


def test_hidden_labels_never_reach_the_engine(universe):
    seen = {}

    def build_kb(rows, lexicon):
        seen["ids"] = {r["id"] for r in rows}
        return {}

    engine = types.SimpleNamespace(**{**vars(ENGINE), "build_kb": build_kb})
    runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=engine)
    hidden = {r["id"] for r in read_output(universe) if not r["type"]}
    assert seen["ids"] and not (seen["ids"] & hidden)


def test_engine_failure_keeps_a_complete_unsure_table(universe):
    def broken(rows, lexicon):
        raise RuntimeError("engine down")

    engine = types.SimpleNamespace(**{**vars(ENGINE), "build_kb": broken})
    status = runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=engine)
    assert status == 1
    rows = read_output(universe)
    assert {r["label"] for r in rows if not r["type"]} == {"unsure"}
    assert sum(1 for r in rows if r["type"]) == 1000


def test_one_failing_row_does_not_stop_the_run(universe):
    def classify(row, extraction, check):
        if row["id"] == "p-1":
            raise ValueError("bad row")
        return ENGINE.classify(row, extraction, check)

    engine = types.SimpleNamespace(**{**vars(ENGINE), "classify": classify})
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=engine) == 0
    by_id = {r["id"]: r for r in read_output(universe) if not r["type"]}
    assert (by_id["p-1"]["label"], by_id["p-1"]["confidence"]) == ("true", "0.8")  # an error: true at the base rate
    assert by_id["p-11"]["label"] == "unsure" and by_id["p-6"]["label"] == "true"  # the others as the engine said


def test_deadline_in_the_past_still_writes_a_table(universe):
    runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE, deadline=0.0)
    rows = read_output(universe)
    assert {r["label"] for r in rows if not r["type"]} == {"unsure"}


def test_the_batch_is_used_when_the_engine_has_one(universe):
    seen = {}

    def label_rows(rows, practice, lexicon, kb=None, extractor=None):
        seen["rows"] = len(rows)  # the whole input, labelled rows included, in file order
        return [{"id": r["id"], "label": "false", "confidence": 0.8} for r in rows if not r["label"]]

    engine = types.SimpleNamespace(**{**vars(ENGINE), "label_rows": label_rows})
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=engine) == 0
    assert seen["rows"] == 1897
    assert {r["label"] for r in read_output(universe) if not r["type"]} == {"false"}


def test_a_failing_batch_falls_back_to_the_same_engine_row_by_row(universe):
    def label_rows(rows, practice, lexicon, kb=None, extractor=None):
        raise RuntimeError("batch broke")

    engine = types.SimpleNamespace(**{**vars(ENGINE), "label_rows": label_rows})
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=engine) == 0
    assert {r["label"] for r in read_output(universe) if not r["type"]} == {"true", "unsure"}  # the fake engine's answers


@pytest.mark.parametrize("content", ["[]", "{not json", '{"events": []}'])
def test_an_unreadable_lexicon_falls_back_to_the_images(universe, content):
    (universe / "universe" / "lexicon.json").write_text(content, encoding="utf-8")
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE) == 0
    rows = read_output(universe)
    assert sum(1 for r in rows if r["type"]) == 1000
    assert len([r for r in rows if not r["type"]]) == 380


def test_a_missing_lexicon_falls_back_to_the_images(universe):
    (universe / "universe" / "lexicon.json").unlink()
    assert runner.load_lexicon(str(universe / "universe"))["subjects"]


def test_lexicon_events_are_kept_as_names(tmp_path):
    (tmp_path / "lexicon.json").write_text(
        '{"subjects": [], "events": ["A", {"name": "B", "date": "2026-01-01"}, {"date": "x"}, 3, null]}', encoding="utf-8")
    assert runner.load_lexicon(str(tmp_path))["events"] == ["A", "B"]
