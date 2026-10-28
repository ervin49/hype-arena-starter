import csv
import json
import os

import pytest

from arena.io import InputError, output_rows, parse_rows, read_lexicon, read_rows, split_rows, write_output

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def test_reads_the_practice_file_with_forms():
    rows = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
    assert len(rows) == 1897
    assert rows[0]["id"] == "p-1"
    assert isinstance(json.loads(rows[0]["form"]), list)
    assert {r["label"] for r in rows} == {"true", "false", "unsure"}


def test_quoted_commas_and_line_breaks():
    data = 'id,text,date,label\nx-1,"One, two\nthree ""quoted"".",2026-04-01,\n'
    [row] = parse_rows(data)
    assert row["text"] == 'One, two\nthree "quoted".'
    assert row["label"] == ""


def test_bom_crlf_semicolons_and_column_case():
    data = "﻿ID;Text;Date;Label\r\nx-1;Hello, world.;2026-04-01;TRUE\r\n".encode("utf-8")
    [row] = parse_rows(data)
    assert row == {"id": "x-1", "text": "Hello, world.", "date": "2026-04-01", "label": "true"}


@pytest.mark.parametrize("data, message", [
    ("", "empty"),
    ("id,text,date\nx,y,2026-01-01\n", "missing columns: label"),
    ("id,text,date,label\nx,a,2026-01-01,\nx,b,2026-01-01,\n", "duplicate id"),
    ("id,text,date,label\nx,a,2026-01-01,maybe\n", "label"),
    ("id,text,date,label\n,a,2026-01-01,\n", "empty id"),
])
def test_rejects_bad_input(data, message):
    with pytest.raises(InputError, match=message):
        parse_rows(data)


def test_split_keeps_order():
    rows = parse_rows("id,text,date,label\na,x,2026-01-01,true\nb,y,2026-01-01,\nc,z,2026-01-01,\n")
    labelled, unlabelled = split_rows(rows)
    assert [r["id"] for r in labelled] == ["a"]
    assert [r["id"] for r in unlabelled] == ["b", "c"]


def test_lexicon():
    lexicon = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
    assert any(s["name"] == "Hooly AI Pro" for s in lexicon["subjects"])
    assert "Hooly I/O 2026" in lexicon["events"]


def test_output_rows_confidence_rules():
    predictions = [
        {"id": "a", "label": "true", "confidence": 0.93456},
        {"id": "b", "label": "unsure", "confidence": 0.7},
        {"id": "c", "label": "false", "confidence": None},  # a verdict with no confidence is not one
        {"id": "d", "label": "false", "confidence": 0.2},   # clamped into [0.5, 1]
        {"id": "a", "label": "false", "confidence": 0.9},   # the first row for an id counts
    ]
    rows = output_rows(predictions, [])
    assert [(r["id"], r["label"], r["confidence"]) for r in rows] == [
        ("a", "true", "0.935"), ("b", "unsure", ""), ("c", "unsure", ""), ("d", "false", "0.5")]


def test_write_output_round_trips_through_the_official_reader(tmp_path):
    claim = {"id": "c-1", "type": "compare", "text": 'Hooly Workspace costs more than Hooly AI Pro, "really".',
             "form": {"left": {"subject": "Hooly Workspace", "attribute": "price"},
                      "right": {"subject": "Hooly AI Pro", "attribute": "price"}, "op": "gt"},
             "label": "true", "confidence": 0.9, "evidence_ids": ["p-1"]}
    out = tmp_path / "output.csv"
    write_output([{"id": "x-1", "label": "unsure", "confidence": None}], [claim], str(out))
    assert os.listdir(tmp_path) == ["output.csv"]  # no temp file left behind
    with open(out, encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0]) == ["id", "type", "text", "form", "label", "confidence"]
    assert rows[0] == {"id": "x-1", "type": "", "text": "", "form": "", "label": "unsure", "confidence": ""}
    assert rows[1]["text"] == claim["text"]
    assert json.loads(rows[1]["form"]) == claim["form"]
    assert (rows[1]["label"], rows[1]["confidence"]) == ("true", "0.9")
