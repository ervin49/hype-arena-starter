"""Test data made by us from the practice rows, in data/test/. Synthetic: not the organisers' data.

- demo.csv + demo_key.csv: ~150 unlabelled rows to upload on the dashboard, each with a known
  answer. Every row is a practice sentence labelled true whose subject is named in it, with one
  fact, and whose answer follows from the labelled-true timeline of that fact:
    true  "restated": the same sentence on another date inside the same run of equal values;
    false "stale":    the same sentence on a date inside a later or earlier run of another value;
    false "inflated": the number changed to one the fact never held, on the original date.
  The sentence wording is real, so the reader understands it; only the date or the number moves.
  The shipped model has seen the original sentences, so this shows the engine working, it does
  not measure it (the honest numbers are out of fold, in STATUS.md).
- holdout.csv + holdout_key.csv: every practice row, every fifth label hidden, as scripts/check.sh
  feeds the image (1,897 rows, uploadable). An upper bound: the model was trained on those rows.
- dense/universe.csv (gitignored): B's 16,403-row density test (scripts/synth_universe.py), for
  the runner only; over the upload limit of 5,000 rows.

    .venv/bin/python scripts/make_test_data.py          # all three
    .venv/bin/python scripts/make_test_data.py --score  # also score demo.csv on the API (port 8000)
"""
import argparse
import csv
import json
import os
import random
import re
import subprocess
import sys
from collections import Counter
from datetime import date

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.generate import Evidence  # noqa: E402
from arena.io import read_rows  # noqa: E402
from arena.values import compatible, parse_values, values_equal  # noqa: E402

OUT = os.path.join(ROOT, "data", "test")
NUMERIC = ("quantity", "money", "percent", "duration")
# a sentence that names its own time can't be moved to another date
# (a present tense such as "now covers" moves with the date: it says the value held on that day)
TIME_WORDS = re.compile(r"\b(19|20)\d\d\b|\b(january|february|march|april|may|june|july|august|september|"
                        r"october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|sept|oct|nov|dec)\b|"
                        r"\b(yesterday|tomorrow|ago|so far|since|until|(this|last|next|previous) "
                        r"(week|month|quarter|year)|quarter|q[1-4])\b", re.I)
PER_KIND = {"restated": 55, "stale": 55, "inflated": 40}


def day(iso):
    return date.fromisoformat(iso).toordinal()


def iso(n):
    return date.fromordinal(n).isoformat()


def names(lexicon):
    """Each subject's name and aliases as whole-word patterns, any case."""
    return {s["name"]: [re.compile(rf"(?<!\w){re.escape(n)}(?!\w)", re.I) for n in [s["name"]] + list(s.get("aliases", []))]
            for s in lexicon["subjects"]}


def candidates(rows, lexicon):
    """Practice rows labelled true with one numeric fact, the subject named, no time words."""
    named = names(lexicon)
    for r in rows:
        if r["label"] != "true" or TIME_WORDS.search(r["text"]):
            continue
        facts = json.loads(r["form"])
        if len(facts) != 1 or facts[0]["value"].get("op") or facts[0]["value"]["kind"] not in NUMERIC:
            continue
        f = facts[0]
        if not any(p.search(r["text"]) for p in named.get(f["subject"], [])):
            continue
        spans = [v for v in parse_values(r["text"]) if v["value"]["kind"] in NUMERIC]
        if len(spans) != 1 or not values_equal(spans[0]["value"], f["value"]):
            continue
        yield r, f, spans[0]


def runs(ev, key):
    """Runs of equal values backed by >= 2 true reports and no labelled lie: (value, first, last)."""
    out = []
    for seg in ev.timelines.get(key, []):
        if seg.n >= 2 and not ev.refuted(key, seg.value, seg.first):
            out.append((seg.value, day(seg.first), day(seg.last)))
    return out


def inside(rng, lo, hi, avoid):
    """A day strictly inside (lo, hi), at least 7 days from `avoid`, or None."""
    days = [d for d in range(lo + 1, hi) if abs(d - avoid) >= 7]
    return rng.choice(days) if days else None


def inflate(value, observed):
    """A number about 1.3x the value, rounded like the original, that the fact never held."""
    v = value["value"]
    if v == 1:  # "2 founder" would not read as English
        return None
    for factor in (1.3, 1.5, 0.7, 2.0):
        n = v * factor
        n = round(n, 2) if isinstance(v, float) and v != int(v) else int(round(n))
        if value["kind"] == "percent" and n > 100:
            continue
        if n != v and not any(values_equal({**value, "value": n}, o) for o in observed):
            return n
    return None


def write_number(raw, old, new):
    """`raw` with its number `old` written as `new`, in the same style (2,600 / 2600 / 3.8)."""
    m = re.search(r"\d[\d,]*(?:\.\d+)?", raw)
    if not m:
        return None
    s = m.group(0)
    if "," in s and "." not in s:
        out = f"{int(new):,}"
    elif "." in s:
        out = f"{new:.{len(s.split('.')[1])}f}"
    else:
        out = str(int(new)) if float(new) == int(new) else str(new)
    return raw[:m.start()] + out + raw[m.end():]


def demo(rows, lexicon, seed=0):
    rng = random.Random(seed)
    ev = Evidence(rows, lexicon, "2026-10-29")
    pool = {"restated": [], "stale": [], "inflated": []}
    for r, f, span in candidates(rows, lexicon):
        key = (f["subject"], f["attribute"])
        d0 = day(r["date"])
        rs = runs(ev, key)
        own = next((x for x in rs if compatible(x[0], f["value"]) and x[1] <= d0 <= x[2]), None)
        observed = [v for _, v, _ in ev.obs.get(key, [])]
        base = {"source_row": r["id"], "fact": f"{key[0]} / {key[1]}", "text": r["text"]}
        if own:
            d = inside(rng, own[1], own[2], d0)
            if d:
                pool["restated"].append({**base, "date": iso(d), "label": "true", "kind": "restated",
                                         "why": f"{span['raw']} held from {iso(own[1])} to {iso(own[2])}"})
            new = inflate(f["value"], observed)
            raw = write_number(span["raw"], f["value"]["value"], new) if new is not None else None
            if raw:
                text = r["text"][:span["start"]] + raw + r["text"][span["end"]:]
                got = [v["value"] for v in parse_values(text) if v["value"]["kind"] in NUMERIC]
                if len(got) == 1 and values_equal(got[0], {**f["value"], "value": new}):
                    pool["inflated"].append({**base, "text": text, "date": r["date"], "label": "false",
                                             "kind": "inflated",
                                             "why": f"{raw} never held; it was {span['raw']} then"})
        for v, lo, hi in rs:
            if compatible(v, f["value"]) or not (lo > d0 or hi < d0):
                continue
            d = inside(rng, lo, hi, d0)
            if d:
                pool["stale"].append({**base, "date": iso(d), "label": "false", "kind": "stale",
                                      "why": f"{span['raw']} was true around {r['date']}; from "
                                             f"{iso(lo)} to {iso(hi)} it was another value"})
                break
    out, used = [], Counter()
    for kind, n in PER_KIND.items():
        rng.shuffle(pool[kind])
        for x in pool[kind]:
            if used[(x["fact"], kind)] or len([y for y in out if y["kind"] == kind]) >= n:
                continue
            used[(x["fact"], kind)] += 1
            out.append(x)
    rng.shuffle(out)
    out.sort(key=lambda x: x["date"])
    for i, x in enumerate(out, 1):
        x["id"] = f"t-{i:03d}"
    return out


def write_csv(path, fields, rows):
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def score(path, key_path):
    """Upload demo.csv to the API, as the dashboard does, and compare with the key."""
    out = subprocess.run(["curl", "-s", "-F", f"file=@{path}", "http://localhost:8000/predict/csv"],
                         capture_output=True, text=True, check=True).stdout
    preds = {p["id"]: p for p in json.loads(out)["predictions"]}
    key = list(csv.DictReader(open(key_path, encoding="utf-8")))
    by = Counter()
    for k in key:
        p = preds.get(k["id"], {})
        by[(k["kind"], p.get("label") == k["label"])] += 1
    for kind in PER_KIND:
        right, n = by[(kind, True)], by[(kind, True)] + by[(kind, False)]
        print(f"  {kind:9} {right}/{n} right")
    total = sum(v for (_, ok), v in by.items() if ok)
    print(f"  all       {total}/{len(key)} right")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--score", action="store_true", help="score demo.csv on the API at port 8000")
    args = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    rows = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
    lexicon = json.load(open(os.path.join(ROOT, "data", "lexicon.json"), encoding="utf-8"))

    d = demo(rows, lexicon)
    write_csv(os.path.join(OUT, "demo.csv"), ["id", "text", "date", "label"], [{**x, "label": ""} for x in d])
    write_csv(os.path.join(OUT, "demo_key.csv"), ["id", "label", "kind", "fact", "why", "source_row", "text", "date"], d)
    print(f"demo.csv: {len(d)} rows, {dict(Counter(x['kind'] for x in d))}")

    hold = [{**r, "label": "" if i % 5 == 0 else r["label"]} for i, r in enumerate(rows)]
    write_csv(os.path.join(OUT, "holdout.csv"), ["id", "text", "date", "label"], hold)
    write_csv(os.path.join(OUT, "holdout_key.csv"), ["id", "label"],
              [{"id": r["id"], "label": r["label"]} for i, r in enumerate(rows) if i % 5 == 0])
    print(f"holdout.csv: {len(hold)} rows, {sum(1 for r in hold if not r['label'])} to check")

    subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "synth_universe.py"), "build",
                    os.path.join(OUT, "dense")], check=True, stdout=subprocess.DEVNULL)
    n = sum(1 for _ in open(os.path.join(OUT, "dense", "universe.csv"), encoding="utf-8")) - 1
    print(f"dense/universe.csv: {n} rows (for the runner: ARENA_UNIVERSE=data/test/dense)")

    if args.score:
        print("demo.csv on the API:")
        score(os.path.join(OUT, "demo.csv"), os.path.join(OUT, "demo_key.csv"))


if __name__ == "__main__":
    main()
