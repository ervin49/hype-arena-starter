"""The engine's contract v1 (hype_arena_PLAN_FINAL.md, section 5) and its
temporal rules, on the synthetic fixture and on the practice data."""

import csv
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.classify import classify, label_rows  # noqa: E402
from arena.extract import build_extractor, extract  # noqa: E402
from arena.truth import build_kb, check_fact  # noqa: E402


def fixture():
    with open(os.path.join(ROOT, "tests", "fixtures_a", "temporal.json"), encoding="utf-8") as f:
        d = json.load(f)
    return d["rows"], d["lexicon"]


def practice():
    with open(os.path.join(ROOT, "data", "practice.csv"), encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8") as f:
        return rows, json.load(f)


def price(v):
    return {"subject": "Acme Widget", "attribute": "price",
            "value": {"kind": "money", "value": v, "currency": "EUR", "per": "month"}}


class TruthTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows, lex = fixture()
        cls.kb = build_kb(rows, lex)

    def check(self, fact, date, exclude=()):
        r = check_fact(fact, date, self.kb, exclude)
        self.assertEqual(set(r) >= {"status", "confidence", "evidence_ids", "reason"}, True)
        self.assertIn(r["status"], ("supported", "contradicted", "unknown"))
        if r["status"] == "unknown":
            self.assertIsNone(r["confidence"])
        return r

    def test_same_day_support(self):
        r = self.check(price(10), "2026-02-10")
        self.assertEqual(r["status"], "supported")
        self.assertIn("fx-2", r["evidence_ids"])

    def test_between_equal_observations(self):
        self.assertEqual(self.check(price(10), "2026-01-25")["status"], "supported")
        self.assertEqual(self.check(price(11), "2026-01-25")["status"], "contradicted")

    def test_value_changes_over_time(self):
        self.assertEqual(self.check(price(12), "2026-06-01")["status"], "supported")
        self.assertEqual(self.check(price(10), "2026-06-01")["status"], "contradicted")

    def test_false_row_is_negative_evidence(self):
        r = self.check(price(99), "2026-02-12")
        self.assertEqual(r["status"], "contradicted")

    def test_exclude_row_ids(self):
        # without the rows that state it, nothing supports 12 on its own day
        r = self.check(price(12), "2026-05-10", exclude=("fx-3",))
        self.assertNotEqual(r["case"], "same_day_match")

    def test_unknown_fact(self):
        fact = {"subject": "Acme Widget", "attribute": "users",
                "value": {"kind": "quantity", "value": 5, "unit": "user"}}
        r = self.check(fact, "2026-01-10")
        self.assertEqual(r["status"], "unknown")
        self.assertIsNone(r["confidence"])

    def test_copies_do_not_confirm_their_own_sentence(self):
        rows, lex = fixture()
        kb = build_kb(rows, lex)
        text = "Acme Widget has 7 users."
        users = {"subject": "Acme Widget", "attribute": "users",
                 "value": {"kind": "quantity", "value": 7, "unit": "user"}}
        stmts = [{"id": "c-1", "text": text, "date": "2026-03-01", "label": ""},
                 {"id": "c-2", "text": text, "date": "2026-03-05", "label": ""},
                 {"id": "c-3", "text": "Widget now has 7 users!", "date": "2026-03-09", "label": ""}]
        kb.add_statements(stmts, [{"facts": [users]}] * 3)
        f = check_fact(users, "2026-03-01", kb, ("c-1",))["features"]
        self.assertTrue(f["u_same"])          # c-3 is another sentence: it counts
        kb2 = build_kb(rows, lex)
        kb2.add_statements(stmts[:2], [{"facts": [users]}] * 2)
        f = check_fact(users, "2026-03-01", kb2, ("c-1",))["features"]
        self.assertFalse(f["u_any"])          # c-2 is a copy of c-1: it does not

    def test_negated_value_inverts_the_check(self):
        # €10 holds on 2026-01-25: "costs €10" is supported, "does not cost €10" contradicted
        said, denied = price(10), dict(price(10), negated=True)
        self.assertEqual(self.check(said, "2026-01-25")["status"], "supported")
        r = self.check(denied, "2026-01-25")
        self.assertEqual((r["status"], r["case"]), ("contradicted", "denied_match"))
        # €11 does not: "costs €11" is contradicted, "does not cost €11" supported
        self.assertEqual(self.check(price(11), "2026-01-25")["status"], "contradicted")
        r = self.check(dict(price(11), negated=True), "2026-01-25")
        self.assertEqual((r["status"], r["case"]), ("supported", "denied_mismatch"))

    def test_negated_fact_is_no_evidence(self):
        rows, lex = fixture()
        rows = rows + [{"id": "fx-n", "text": "Acme Widget does not cost €11 per month.", "date": "2026-01-20",
                        "label": "true", "form": json.dumps([dict(price(11), negated=True)])}]
        kb = build_kb(rows, lex)
        self.assertEqual(check_fact(price(11), "2026-01-20", kb)["status"], "contradicted")
        self.assertNotIn("fx-n", check_fact(price(10), "2026-01-20", kb)["evidence_ids"])

    def test_partial_date_is_stable(self):
        fact = {"subject": "Acme Widget", "attribute": "launched",
                "value": {"kind": "date", "value": "2025-03"}}
        self.assertEqual(self.check(fact, "2026-09-01")["status"], "supported")


class ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows, cls.lex = practice()
        cls.kb = build_kb(cls.rows, cls.lex)
        cls.ex = build_extractor(cls.rows, cls.lex)

    def test_extract_shape(self):
        row = {"id": "t-1", "text": "Hooly AI Pro costs €59 per month.", "date": "2026-10-20", "label": ""}
        out = extract(row, self.lex, self.ex)
        self.assertEqual(set(out) >= {"facts", "complete", "issues"}, True)
        self.assertEqual(out["facts"][0], {"subject": "Hooly AI Pro", "attribute": "price",
                                           "value": {"kind": "money", "value": 59,
                                                     "currency": "EUR", "per": "month"}})

    def test_extract_negated_value(self):
        said = extract({"id": "t-6", "text": "Hooly AI Pro costs €59 per month.", "date": "2026-10-20",
                        "label": ""}, self.lex, self.ex, context=[])
        denied = extract({"id": "t-7", "text": "Hooly AI Pro does not cost €59 per month.",
                          "date": "2026-10-20", "label": ""}, self.lex, self.ex, context=[])
        self.assertNotIn("negated", said["facts"][0])
        self.assertTrue(denied["facts"][0]["negated"])
        self.assertEqual(denied["facts"][0]["value"], said["facts"][0]["value"])

    def test_classify_shape(self):
        check = lambda fact, date: check_fact(fact, date, self.kb)
        for text in ("Hooly AI Pro costs €59 per month.", "The weather is nice."):
            row = {"id": "t-2", "text": text, "date": "2026-10-20", "label": ""}
            p = classify(row, extract(row, self.lex, self.ex), check)
            self.assertEqual(set(p) >= {"id", "label", "confidence", "evidence_ids", "reason"}, True)
            self.assertEqual(p["id"], "t-2")
            self.assertIn(p["label"], ("true", "false", "unsure"))
            if p["label"] == "unsure":
                self.assertIsNone(p["confidence"])
            else:
                self.assertTrue(0.5 <= p["confidence"] <= 1)
            json.dumps(p)

    def test_label_rows_skips_labelled(self):
        rows = [dict(self.rows[0]),
                {"id": "t-3", "text": "Hooly AI Pro costs €49 per month.", "date": "2026-10-20", "label": ""}]
        out = label_rows(rows, self.rows, self.lex, self.kb, self.ex)
        self.assertEqual([p["id"] for p in out], ["t-3"])
        self.assertIn("extraction", out[0])

    def test_label_rows_ensemble(self):
        rows = [dict(self.rows[0]),
                {"id": "t-4", "text": "Hooly AI Pro costs €49 per month.", "date": "2026-10-20", "label": ""},
                {"id": "t-5", "text": "The weather is nice.", "date": "2026-10-20", "label": ""}]
        single = label_rows(rows, self.rows, self.lex, self.kb, self.ex)
        out = label_rows(rows, self.rows, self.lex, self.kb, self.ex, ensemble=True)
        self.assertEqual([p["id"] for p in out], ["t-4", "t-5"])
        self.assertTrue(all("spread" not in p for p in single))
        for p in out:
            self.assertTrue(0 <= p["spread"] <= 1)
            self.assertIn(p["label"], ("true", "false", "unsure"))
            if p["label"] != "unsure":
                self.assertTrue(0.5 <= p["confidence"] <= 1)
            json.dumps({k: v for k, v in p.items() if k != "_raw_checks"})


if __name__ == "__main__":
    unittest.main()
