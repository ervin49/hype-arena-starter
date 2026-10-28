"""Backtest the claim generator: how often is each group of claims right on data it has not seen?

For each cut-off date, claims are generated from the practice rows before it (as-of two weeks
after the cut-off) and judged against every practice row, the later ones included:

- fact (date), compare (dates): the date as reported after it passed;
- fact (other), compare (amounts): the values reported in the 45 days after the as-of date;
- change: the full timeline holds `from` before `to`;
- at_event: the values reported last before and first after the event's date;
- relation: not judged (too few claims, and the link's validity is not observable).

A claim with no later evidence is "unknown" and does not count. Writes
reports/claims_calibration.json, which arena.generate reads: a group is kept when it is at
least MIN_GROUP_PRECISION right at every cut-off where it was judged on 10+ claims, and its
confidence is the Wilson lower bound (95%) of its pooled precision, never above what we measured.

    .venv/bin/python scripts/backtest_claims.py
"""
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.generate import (CALIBRATION, MIN_GROUP_PRECISION, UNMEASURED_CONFIDENCE,  # noqa: E402
                            Evidence, select_claims)
from arena.io import read_lexicon, read_rows  # noqa: E402
from arena.values import canonical_amount, compatible, date_interval  # noqa: E402

CUTOFFS = ["2026-05-01", "2026-07-01", "2026-09-01"]
AS_OF_AFTER_DAYS = 14
WINDOW_DAYS = 45
MIN_JUDGED = 20       # fewer judged claims than this: the group is "not measured"
MIN_PER_CUTOFF = 10   # a cut-off counts against a group only with this many judged claims


def wilson_lower(right, n, z=1.96):
    if n == 0:
        return 0.0
    p = right / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)


class Judge:
    def __init__(self, rows, lexicon, as_of):
        self.full = Evidence(rows, lexicon, "2026-10-29")
        self.as_of = as_of
        self.end = (date.fromisoformat(as_of) + timedelta(days=WINDOW_DAYS)).isoformat()
        self.events = self.full.event_dates()

    def obs(self, key):
        return sorted(self.full.obs.get(key, []), key=lambda o: o[0])

    def near(self, key):
        return [v for d, v, _ in self.obs(key) if self.as_of <= d <= self.end]

    def __call__(self, c):
        f, t, g = c["form"], c["type"], c["group"]
        if t == "fact":
            key = (f["subject"], f["attribute"])
            if g == "fact.date":
                got = self.full.past_date(key)
                return None if not got else compatible(got[0], f["value"])
            near = self.near(key)
            return None if not near else all(compatible(v, f["value"]) for v in near)
        if t == "compare":
            left = (f["left"]["subject"], f["left"]["attribute"])
            right = (f["right"]["subject"], f["right"]["attribute"])
            if g == "compare.date":
                a, b = self.full.past_date(left), self.full.past_date(right)
                if not a or not b:
                    return None
                (a0, a1), (b0, b1) = date_interval(a[0]["value"]), date_interval(b[0]["value"])
                return a1 < b0 if f["op"] == "lt" else b1 < a0
            la, ra = self.near(left), self.near(right)
            if not la or not ra:
                return None
            x, y = canonical_amount(la[-1]), canonical_amount(ra[-1])
            if not x or not y:
                return None
            return {"gt": x[1] > y[1], "lt": x[1] < y[1], "eq": x[1] == y[1]}[f["op"]]
        if t == "change":
            segs = self.full.timelines.get((f["subject"], f["attribute"]), [])
            i = [k for k, s in enumerate(segs) if compatible(s.value, f["from"])]
            j = [k for k, s in enumerate(segs) if compatible(s.value, f["to"])]
            return bool(i and j and min(i) < max(j))
        if t == "at_event":
            ev = self.events.get(f["event"])
            if not ev:
                return None
            e = ev[0]["value"]
            o = self.obs((f["subject"], f["attribute"]))
            before = [v for d, v, _ in o if d <= e]
            after = [v for d, v, _ in o if d >= e]
            if not before or not after:
                return None
            return compatible(before[-1], f["value"]) and compatible(after[0], f["value"])
        return None


def backtest(rows, lexicon):
    texts = [r["text"] for r in rows]
    per_cut = {}
    for cut in CUTOFFS:
        as_of = (date.fromisoformat(cut) + timedelta(days=AS_OF_AFTER_DAYS)).isoformat()
        train = [r for r in rows if r["date"] < cut]
        claims, _ = select_claims(train, lexicon, as_of, texts, 5000, calibration=None)
        judge = Judge(rows, lexicon, as_of)
        tally = defaultdict(lambda: {"right": 0, "wrong": 0, "unknown": 0})
        for c in claims:
            v = judge(c)
            tally[c["group"]]["right" if v else "wrong" if v is False else "unknown"] += 1
        per_cut[cut] = tally
    return per_cut


def calibration(per_cut):
    groups = sorted({g for t in per_cut.values() for g in t})
    out = []
    for g in groups:
        cuts = {cut: dict(per_cut[cut].get(g, {"right": 0, "wrong": 0, "unknown": 0})) for cut in CUTOFFS}
        right = sum(c["right"] for c in cuts.values())
        judged = right + sum(c["wrong"] for c in cuts.values())
        for c in cuts.values():
            n = c["right"] + c["wrong"]
            c["precision"] = round(c["right"] / n, 3) if n else None
        if judged < MIN_JUDGED:
            keep, conf, note = True, UNMEASURED_CONFIDENCE, "not measured: too few claims judged"
        else:
            precision = right / judged
            worst = min((c["precision"] for c in cuts.values()
                         if c["precision"] is not None and c["right"] + c["wrong"] >= MIN_PER_CUTOFF), default=precision)
            keep = precision >= MIN_GROUP_PRECISION and worst >= MIN_GROUP_PRECISION
            conf = round(min(0.99, max(0.5, wilson_lower(right, judged))), 3)
            note = "kept" if keep else f"dropped: {precision:.0%} right overall, {worst:.0%} at its worst cut-off"
        out.append({"group": g, "n": judged, "right": right,
                    "precision": round(right / judged, 3) if judged else None,
                    "keep": keep, "confidence": conf, "note": note, "cutoffs": cuts})
    return out


def main():
    rows = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
    lexicon = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
    groups = calibration(backtest(rows, lexicon))
    os.makedirs(os.path.dirname(CALIBRATION), exist_ok=True)
    with open(CALIBRATION, "w", encoding="utf-8") as f:
        json.dump({"cutoffs": CUTOFFS, "as_of_after_days": AS_OF_AFTER_DAYS, "window_days": WINDOW_DAYS,
                   "min_group_precision": MIN_GROUP_PRECISION, "confidence": "Wilson lower bound (95%), pooled",
                   "groups": groups}, f, indent=1)
        f.write("\n")
    print(f"{'group':16} {'judged':>6} {'right':>6} {'prec':>6} {'conf':>6}  per cut-off            decision")
    for g in groups:
        per = " ".join(f"{c['precision'] if c['precision'] is not None else '  -  ':>5}" for c in g["cutoffs"].values())
        print(f"{g['group']:16} {g['n']:6} {g['right']:6} {g['precision'] or 0:6.3f} {g['confidence']:6.3f}  {per:22} {g['note']}")
    print(f"wrote {os.path.relpath(CALIBRATION, ROOT)}")


if __name__ == "__main__":
    main()
