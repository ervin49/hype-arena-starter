"""scripts/referee.py against every example of contracts/value-forms.md and contracts/claim-forms.md.

The examples are read from the two files, so the tests follow the spec as it stands.
"""
import json
import os
import re
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import referee as R  # noqa: E402


def tables(path):
    """[(section, header cells, [row cells])] of every table in a markdown file."""
    out, section, cur = [], "", None
    for line in open(path, encoding="utf-8").read().splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        if line.startswith("|"):
            cells = [c.strip() for c in re.split(r"(?<!\\)\|", line.strip())[1:-1]]
            if cur is None:
                cur = (section, cells, [])
                out.append(cur)
            elif not set("".join(cells)) <= set("- :"):
                cur[2].append(cells)
        else:
            cur = None
    return out


def code(cell):
    m = re.fullmatch(r"`(.*)`", cell)
    return m.group(1) if m else cell


VALUE_FORMS = os.path.join(ROOT, "contracts", "value-forms.md")
CLAIM_FORMS = os.path.join(ROOT, "contracts", "claim-forms.md")
TEST_LEXICON = R.Lexicon({"subjects": [
    {"name": "Hooly", "aliases": [], "attributes": ["soc2_certified", "profitable", "cto", "founded_by"]},
    {"name": "Hooly AI Pro", "aliases": [], "attributes": ["price"]},
    {"name": "Hooly Workspace", "aliases": ["Workspace"], "attributes": ["price"]},
    {"name": "Hooly AI Free", "aliases": [], "attributes": ["price"]},
    {"name": "Hooly Gemini", "aliases": [], "attributes": ["languages"]},
    {"name": "Hooly I/O 2026", "aliases": ["Hooly I/O"], "attributes": ["date"]},
    {"name": "The May 2026 outage", "aliases": ["outage"], "attributes": ["date"]},
    {"name": "Bertram Gilfoil", "aliases": [], "attributes": ["joined"]},
    {"name": "Richard Hendrix", "aliases": [], "attributes": ["joined"]},
    {"name": "Gavin Bellson", "aliases": [], "attributes": ["joined"]},
], "events": ["Hooly I/O 2026", "The May 2026 outage"]})
KINDS = {"price": {"money"}, "date": {"date"}, "languages": {"quantity"}, "joined": {"date"}}


def value_examples(header):
    return [(t[0], cells) for t in tables(VALUE_FORMS) if t[1][:2] == header for cells in t[2]]


READ = value_examples(["Written", "Read as"])
NOT_READ = value_examples(["Written", "Does not state"])


def states(written, value):
    if value["kind"] == "name":
        hits = TEST_LEXICON.find(written)
        return any(c == value["value"] and not R.negated_before(written, a) for a, _, c in hits)
    if value["kind"] == "boolean":
        return R.has_negation(written) == (value["value"] is False)
    for v in R.Reader(written).values:
        if v["approx"] or v["range"] or (v["negated"] and value["kind"] != "boolean"):
            continue
        if (v["op"] or "eq") == value.get("op", "eq") and R.same_value(v["value"], value):
            return True
    return False


def test_the_tables_are_found():
    assert len(READ) >= 90 and len(NOT_READ) >= 30


@pytest.mark.parametrize("section,cells", READ, ids=[f"{s}: {c[0]}" for s, c in READ])
def test_read_as(section, cells):
    written, value = code(cells[0]), json.loads(code(cells[1]))
    assert states(written, value), f"{written!r} should state {value}; read {[v['value'] for v in R.Reader(written).values]}"


@pytest.mark.parametrize("section,cells", NOT_READ, ids=[c[0] for _, c in NOT_READ])
def test_not_read(section, cells):
    written, value = code(cells[0]), json.loads(code(cells[1]))
    assert not states(written, value), f"{written!r} should not state {value}"


# claim-forms.md: the form of each table, in the order the tables come in their section
PRICE = {"kind": "money", "value": 59, "currency": "EUR", "per": "month"}
FORMS = {
    "Fact": [("fact", {"subject": "Hooly AI Pro", "attribute": "price", "value": PRICE}),
             ("fact", {"subject": "Hooly", "attribute": "soc2_certified", "value": {"kind": "boolean", "value": False}})],
    "Compare": [("compare", {"left": {"subject": "Hooly Workspace", "attribute": "price"},
                             "right": {"subject": "Hooly AI Pro", "attribute": "price"}}),
                ("compare", {"left": {"subject": "Hooly I/O 2026", "attribute": "date"},
                             "right": {"subject": "The May 2026 outage", "attribute": "date"}})],
    "Change": [("change", {"subject": "Hooly AI Pro", "attribute": "price",
                           "from": {"kind": "money", "value": 49, "currency": "EUR", "per": "month"}, "to": PRICE})],
    "At an event": [("at_event", {"subject": "Hooly Gemini", "attribute": "languages", "event": "Hooly I/O 2026",
                                  "value": {"kind": "quantity", "value": 12, "unit": "language"}})],
    "Relation": [("relation", {"subject": "Hooly", "link": "cto", "target": "Bertram Gilfoil", "attribute": "joined",
                               "value": {"kind": "date", "value": "2026-07-01"}})],
}


def claim_examples():
    seen, out = {}, []
    for section, header, rows in tables(CLAIM_FORMS):
        if header[0] != "Text":
            continue
        i = seen.get(section, 0)
        seen[section] = i + 1
        typ, form = FORMS[section][i]
        for cells in rows:
            f = dict(form)
            if header[1] == "`op`":
                f["op"] = code(cells[1])
            out.append((section, typ, f, code(cells[0]), cells[-1]))
    return out


CLAIMS = claim_examples()


def test_every_claim_table_is_read():
    assert len(CLAIMS) >= 70 and {c[0] for c in CLAIMS} == set(FORMS)


@pytest.mark.parametrize("section,typ,form,text,read", CLAIMS, ids=[f"{c[0]}: {c[3]}" for c in CLAIMS])
def test_claim_forms(section, typ, form, text, read):
    errs = R.Referee(TEST_LEXICON, KINDS).check(typ, form, text)
    if read.startswith("yes"):
        assert errs == [], errs
    else:
        assert errs, f"{text!r} should be rejected ({read})"


def test_the_good_entries_pass_the_schema_and_the_bad_ones_fail():
    v = R.schema_validator()
    folder = os.path.join(ROOT, "contracts", "examples", "entry")
    for name in os.listdir(os.path.join(folder, "good")):
        assert not list(v.iter_errors(json.load(open(os.path.join(folder, "good", name))))), name
    for name in os.listdir(os.path.join(folder, "bad")):
        assert list(v.iter_errors(json.load(open(os.path.join(folder, "bad", name))))), name


def test_a_name_value_matches_its_words_even_outside_the_lexicon():
    ref = R.Referee(TEST_LEXICON, KINDS)
    city = {"kind": "name", "value": "Lisbon"}
    form = {"subject": "Hooly Gemini", "attribute": "languages", "event": "Hooly I/O 2026", "value": city}
    assert ref.check("at_event", form, "Hooly Gemini city was LISBON at the time of Hooly I/O 2026.") == []
    assert ref.check("at_event", form, "Hooly Gemini city was Lisbonia at the time of Hooly I/O 2026.")
    change = {"subject": "Hooly", "attribute": "cto", "from": {"kind": "name", "value": "Richard Hendrix"},
              "to": {"kind": "name", "value": "Bertram Gilfoil"}}
    assert ref.check("change", change, "Hooly CTO went from Richard Hendrix to Bertram Gilfoil.") == []
    assert ref.check("change", change, "Hooly CTO went from Bertram Gilfoil to Richard Hendrix.")
    assert ref.check("change", change, "Hooly CTO went up from Richard Hendrix to Bertram Gilfoil.")


def test_a_name_inside_a_longer_name_names_that_one_only():
    ref = R.Referee(TEST_LEXICON, KINDS)
    form = {"subject": "Hooly Gemini", "attribute": "languages", "event": "Hooly I/O 2026",
            "value": {"kind": "name", "value": "Hooly"}}
    assert ref.check("at_event", form, "Hooly Gemini owner was Hooly AI Pro at the time of Hooly I/O 2026.")


def test_a_claim_unit_in_any_listed_spelling():
    for unit in ("in", "inch", "inches"):
        assert R.same_value(R.Reader("a 6.1-inch display").values[0]["value"], {"kind": "quantity", "value": 6.1, "unit": unit})
    assert R.same_value(R.Reader("2 terabytes").values[0]["value"], {"kind": "quantity", "value": 2000, "unit": "gigabyte"})
    assert not R.same_value(R.Reader("8 inches").values[0]["value"], {"kind": "quantity", "value": 8, "unit": "cm"})
