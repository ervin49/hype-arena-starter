"""The value parser against every example table of contracts/value-forms.md.

Names and yes-or-no values are read by the extractor, not by the parser, so
those sections are skipped here.
"""

import json
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.values import compatible, parse_values, satisfies, values_equal  # noqa: E402

SKIP_SECTIONS = {"Name", "Yes or no"}


def examples():
    with open(os.path.join(ROOT, "contracts", "value-forms.md"), encoding="utf-8") as f:
        md = f.read()
    section = None
    for line in md.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
        m = re.match(r"\| `(.+?)` \| `(\{.+?\})` \|", line)
        if m and section not in SKIP_SECTIONS:
            yield section, m.group(1), json.loads(m.group(2))


def reads(text, value):
    for g in parse_values(text):
        if g["approx"] or g["range"] or g["negated"]:
            continue
        if values_equal(g["value"], value) and g["value"].get("op") == value.get("op"):
            return True
    return False


class ValueFormsTest(unittest.TestCase):
    def test_tables(self):
        n = 0
        for section, text, value in examples():
            n += 1
            with self.subTest(section=section, text=text, value=value):
                self.assertEqual(reads(text, value), section != "Not read")
        self.assertGreater(n, 100)

    def test_units_convert(self):
        self.assertTrue(values_equal({"kind": "quantity", "value": 1, "unit": "GB"},
                                     {"kind": "quantity", "value": 1000, "unit": "MB"}))
        self.assertTrue(values_equal({"kind": "duration", "value": 14, "unit": "day"},
                                     {"kind": "duration", "value": 2, "unit": "week"}))
        self.assertFalse(values_equal({"kind": "duration", "value": 30, "unit": "day"},
                                      {"kind": "duration", "value": 1, "unit": "month"}))
        self.assertFalse(values_equal({"kind": "money", "value": 49, "currency": "EUR", "per": "month"},
                                      {"kind": "money", "value": 49, "currency": "EUR"}))

    def test_partial_dates(self):
        self.assertTrue(compatible({"kind": "date", "value": "2025-11"},
                                   {"kind": "date", "value": "2025-11-03"}))
        self.assertFalse(values_equal({"kind": "date", "value": "2025-11"},
                                      {"kind": "date", "value": "2025-11-03"}))

    def test_constraints(self):
        over = {"kind": "quantity", "value": 100, "unit": "customer", "op": "gt"}
        self.assertTrue(satisfies({"kind": "quantity", "value": 150, "unit": "customer"}, over))
        self.assertFalse(satisfies({"kind": "quantity", "value": 80, "unit": "customer"}, over))

    def test_name_is_masked(self):
        # "the 2026 of Hooly I/O 2026 states no year"
        text = "Hooly I/O 2026 had 1,200 attendees."
        start = text.index("Hooly I/O 2026")
        vals = parse_values(text, [(start, start + len("Hooly I/O 2026"))])
        self.assertEqual([v["value"]["kind"] for v in vals], ["quantity"])


if __name__ == "__main__":
    unittest.main()
