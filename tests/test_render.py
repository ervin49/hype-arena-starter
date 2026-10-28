import csv
import json
import os

import pytest

from arena.render import plural, render_value
from arena.values import parse_values

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.mark.parametrize("value, text", [
    ({"kind": "money", "value": 59, "currency": "EUR", "per": "month"}, "€59 per month"),
    ({"kind": "money", "value": 1200, "currency": "EUR"}, "€1,200"),
    ({"kind": "money", "value": 299.99, "currency": "USD"}, "$299.99"),
    ({"kind": "money", "value": 1999, "currency": "RON"}, "RON 1,999"),
    ({"kind": "quantity", "value": 2026, "unit": "customer"}, "2,026 customers"),  # not a year
    ({"kind": "quantity", "value": 1, "unit": "seat"}, "1 seat"),
    ({"kind": "quantity", "value": 21, "unit": "country"}, "21 countries"),
    ({"kind": "quantity", "value": 128, "unit": "GB"}, "128 GB"),
    ({"kind": "quantity", "value": 6.3, "unit": "inch"}, "6.3 inches"),
    ({"kind": "percent", "value": 99.95}, "99.95%"),
    ({"kind": "date", "value": "2025-11-04"}, "4 November 2025"),
    ({"kind": "date", "value": "2025-11"}, "November 2025"),
    ({"kind": "date", "value": "2025"}, "2025"),
    ({"kind": "version", "value": "2.3"}, "version 2.3"),
    ({"kind": "duration", "value": 18, "unit": "min"}, "18 minutes"),
    ({"kind": "duration", "value": 1, "unit": "day"}, "1 day"),
    ({"kind": "name", "value": "Bertram Gilfoil"}, "Bertram Gilfoil"),
])
def test_render(value, text):
    assert render_value(value) == text


@pytest.mark.parametrize("value", [
    {"kind": "quantity", "value": 100, "unit": "customer", "op": "gt"},  # a claim's value has no op
    {"kind": "duration", "value": 0.8571428571428571, "unit": "week"},  # no exact written form
    {"kind": "quantity", "value": 1.5, "unit": "GB"} | {"value": 1.125},  # three decimals read as nothing
    {"kind": "boolean", "value": True},  # written by the templates
])
def test_refuses_what_cannot_read_back(value):
    assert render_value(value) is None


def test_plural():
    assert [plural(w) for w in ["region", "company", "watch", "day", "person"]] == \
        ["regions", "companies", "watches", "days", "people"]


def test_every_practice_value_reads_back_exactly():
    """Render each value of the practice forms, read it with the engine's independent parser."""
    seen, checked = set(), 0
    with open(os.path.join(ROOT, "data", "practice.csv"), encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            for fact in json.loads(row["form"]):
                v = fact["value"]
                key = json.dumps(v, sort_keys=True)
                if key in seen or "op" in v or v["kind"] in ("boolean", "name"):
                    continue
                seen.add(key)
                text = render_value(v)
                if text is None:
                    continue
                got = [p["value"] for p in parse_values(f"Hooly has {text}.")
                       if not (p["approx"] or p["range"] or p["negated"])]
                assert got == [v], (v, text, got)
                checked += 1
    assert checked >= 720
