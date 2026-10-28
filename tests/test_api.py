import types

import pytest
from fastapi.testclient import TestClient

from api.main import create_app
from tests.fixtures_c.fake_engine import ENGINE

ROW = {"id": "demo-2", "text": "Hooly AI Pro costs €59 per month.", "date": "2026-04-01", "label": ""}


def client(**kwargs):
    return TestClient(create_app(**kwargs))


@pytest.fixture
def api():
    with client(engine=ENGINE, demo=False) as c:
        yield c


def test_health(api):
    assert api.get("/health").json() == {"status": "ok", "demo_mode": False}


def test_predict_follows_the_contract(api):
    body = api.post("/predict", json={"rows": [ROW]}).json()
    assert body["demo_mode"] is False
    [p] = body["predictions"]
    assert p["id"] == "demo-2" and p["label"] == "true" and p["confidence"] == 0.75
    assert set(p) >= {"id", "label", "confidence", "evidence_ids", "reason", "extraction"}
    assert set(p["extraction"]) == {"facts", "complete", "issues"}


def test_predict_skips_labelled_rows(api):
    rows = [ROW, {**ROW, "id": "known", "label": "true"}]
    assert [p["id"] for p in api.post("/predict", json={"rows": rows}).json()["predictions"]] == ["demo-2"]


@pytest.mark.parametrize("body", [
    {"rows": []},
    {"rows": [{**ROW, "date": "01/04/2026"}]},
    {"rows": [{**ROW, "label": "maybe"}]},
    {"rows": [{**ROW, "text": ""}]},
    {"rows": [ROW, ROW]},
    {},
])
def test_predict_rejects_bad_requests(api, body):
    assert api.post("/predict", json=body).status_code == 422


def test_predict_csv_parses_quotes_and_keeps_labelled_rows(api):
    csv = ('id,text,date,label\n'
           'a-1,"Hooly, the company, has\n12 offices.",2026-04-01,\n'
           'a-2,Known row.,2026-04-01,true\n')
    r = api.post("/predict/csv", files={"file": ("sample.csv", csv.encode(), "text/csv")})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["rows"] == [
        {"id": "a-1", "text": "Hooly, the company, has\n12 offices.", "date": "2026-04-01", "label": ""},
        {"id": "a-2", "text": "Known row.", "date": "2026-04-01", "label": "true"}]
    assert [p["id"] for p in body["predictions"]] == ["a-1"]
    assert body["demo_mode"] is False


@pytest.mark.parametrize("csv, status", [
    (b"id,text,date\nx,y,2026-01-01\n", 422),
    (b"id,text,date,label\nx,y,1 April,\n", 422),
    (b"\xff\xfe broken", 422),
    (b"id,text,date,label\n" + b"x" * (5 * 1024 * 1024), 413),
])
def test_predict_csv_rejects_bad_files(api, csv, status):
    r = api.post("/predict/csv", files={"file": ("bad.csv", csv, "text/csv")})
    assert r.status_code == status, r.text
    assert r.json()["detail"]


def test_missing_engine_is_an_error_not_a_fake_answer():
    def broken(rows, lexicon):
        raise ImportError("No module named 'arena.truth'")

    with client(engine=types.SimpleNamespace(**{**vars(ENGINE), "build_kb": broken}), demo=False) as c:
        r = c.get("/health")
        assert r.status_code == 503 and "arena.truth" in r.json()["detail"]
        assert c.post("/predict", json={"rows": [ROW]}).status_code == 503


def test_a_failing_row_is_reported(api):
    def classify(row, extraction, check):
        raise ValueError("boom")

    with client(engine=types.SimpleNamespace(**{**vars(ENGINE), "classify": classify}), demo=False) as c:
        [p] = c.post("/predict", json={"rows": [ROW]}).json()["predictions"]
    assert p["label"] == "unsure" and p["confidence"] is None and "boom" in p["error"]


def test_demo_mode_is_explicit():
    with client(demo=True) as c:
        assert c.get("/health").json()["demo_mode"] is True
        assert c.post("/predict", json={"rows": [ROW]}).json()["demo_mode"] is True
