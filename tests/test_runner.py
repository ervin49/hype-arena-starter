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


def test_failing_claim_generation_falls_back_to_the_claims_file(universe, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("generator down")

    monkeypatch.setitem(sys.modules, "arena.generate", types.SimpleNamespace(select_claims=broken))
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE) == 0
    rows = read_output(universe)
    claims = [r for r in rows if r["type"]]
    assert len(claims) == 1000 and claims[0]["id"] == "gh-0001"
    labels = [r for r in rows if not r["type"]]
    assert len(labels) == 380 and all(r["label"] in ("true", "false", "unsure") for r in labels)
    assert {r["label"] for r in labels} != {"unsure"}  # the engine still labelled them


def test_the_first_table_is_written_before_the_claims(universe, monkeypatch):
    seen = {}

    def spy(practice, lexicon, as_of, input_texts, n):
        seen["rows"] = read_output(universe)
        return fake_claims(practice, lexicon, as_of, input_texts, n)

    monkeypatch.setitem(sys.modules, "arena.generate", types.SimpleNamespace(select_claims=spy))
    runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE)
    assert len(seen["rows"]) == 380 and {r["label"] for r in seen["rows"]} == {"unsure"}


def test_the_fallback_file_is_what_the_run_writes_on_practice(tmp_path):
    """data/claims_fallback.csv is the run's own claims on practice: regenerate it
    (scripts/claims_fallback.py) when the generator changes."""
    (tmp_path / "universe").mkdir()
    (tmp_path / "output").mkdir()
    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "input.py"), PRACTICE,
                    str(tmp_path / "universe" / "universe.csv")], check=True, capture_output=True)
    shutil.copy(os.path.join(ROOT, "data", "lexicon.json"), tmp_path / "universe")
    runner.run(str(tmp_path / "universe"), str(tmp_path / "output"), PRACTICE, engine=ENGINE)
    ran = [(r["id"], r["text"], r["form"]) for r in read_output(tmp_path) if r["type"]]
    fallback = [(c["id"], c["text"], c["form"]) for c in runner.read_claims_fallback(runner.CLAIMS_FALLBACK)]
    assert len(ran) == 1000 and ran == fallback


def test_bad_rows_in_the_input_cost_only_those_rows(universe):
    with open(universe / "universe" / "universe.csv", "a", encoding="utf-8") as f:
        f.write("p-1,A repeated id.,2026-01-02,\n,No id.,2026-01-03,\nx-1,Odd label.,2026-01-04,maybe\n")
    assert runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE) == 0
    rows = read_output(universe)
    labels = {r["id"] for r in rows if not r["type"]}
    assert len(labels) == 381 and "x-1" in labels  # the 380 hidden rows and the cleared label
    assert sum(1 for r in rows if r["type"]) == 1000


def _universe_rows(universe):
    with open(universe / "universe" / "universe.csv", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def _write_universe(universe, rows):
    with open(universe / "universe" / "universe.csv", "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "date", "label"])
        w.writeheader()
        w.writerows(rows)


def test_renumbered_practice_rows_are_found_by_text_and_date(universe):
    practice = runner.read_rows(PRACTICE, require_form=True)
    rows = _universe_rows(universe)
    by_id = runner.known_practice(practice, rows)
    assert len(by_id) == 1517  # every fifth label hidden
    assert runner.remap_practice_ids(rows, practice) == (rows, 0)  # ids found: nothing changes
    renamed = [{**r, "id": "u-" + r["id"]} for r in rows]
    remapped, n = runner.remap_practice_ids(renamed, practice)
    assert n == 1517
    assert {r["id"] for r in remapped if not r["label"]} == {r["id"] for r in renamed if not r["label"]}
    assert [r["id"] for r in runner.known_practice(practice, remapped)] == [r["id"] for r in by_id]
    unrelated = [{"id": "x", "text": "Nothing like practice.", "date": "2026-01-01", "label": "true"}]
    assert len(runner.known_practice(practice, unrelated)) == len(practice)


def test_renumbered_practice_ids_give_the_same_labels(universe):
    """The real engine: an input whose ids are all renamed is labelled as the plain one."""
    runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE)
    plain = {r["id"]: (r["label"], r["confidence"]) for r in read_output(universe) if not r["type"]}
    _write_universe(universe, [{**r, "id": "u-" + r["id"]} for r in _universe_rows(universe)])
    runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE)
    renamed = {r["id"][2:]: (r["label"], r["confidence"]) for r in read_output(universe) if not r["type"]}
    assert renamed == plain and {lab for lab, _ in plain.values()} == {"true", "false"}


def test_undated_rows_cost_only_those_rows(universe):
    """The real engine: rows dated "", "2026-02-30" and "12/03/2026" are true at the base rate;
    the batch and the confidence control still run for every other row."""
    rows = _universe_rows(universe)
    bad = {"": "", "2026-02-30": "", "12/03/2026": ""}
    extra = [{"id": f"bad-{i}", "text": "Hooly Cloud covers 8 regions.", "date": d, "label": ""}
             for i, d in enumerate(bad)]
    _write_universe(universe, rows + extra)
    log = []
    orig = runner.log
    runner.log = lambda *a: (log.append(" ".join(map(str, a))), orig(*a))
    try:
        runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE)
    finally:
        runner.log = orig
    out = {r["id"]: r for r in read_output(universe) if not r["type"]}
    assert all((out[f"bad-{i}"]["label"], out[f"bad-{i}"]["confidence"]) == ("true", "0.8") for i in range(3))
    assert any(m.startswith("batch:") for m in log), log
    assert any(m.startswith("confidence control:") for m in log), log
    assert {out[r["id"]]["label"] for r in rows if not r["label"]} == {"true", "false"}


def test_sigterm_is_never_swallowed_by_a_fallback(universe, monkeypatch):
    def stopped(*args, **kwargs):
        raise runner.Stop()

    monkeypatch.setitem(sys.modules, "arena.generate", types.SimpleNamespace(select_claims=stopped))
    with pytest.raises(runner.Stop):  # not caught by the claims fallback's `except Exception`
        runner.run(str(universe / "universe"), str(universe / "output"), PRACTICE, engine=ENGINE)
    rows = read_output(universe)
    assert len(rows) == 380 and {r["label"] for r in rows} == {"unsure"}  # the first table stands
    assert issubclass(runner.Stop, BaseException) and not issubclass(runner.Stop, Exception)
