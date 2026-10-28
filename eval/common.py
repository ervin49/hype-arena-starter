"""Shared helpers for the engine's evaluation: data loading and folds.

Folds are grouped by page: a page is a run of consecutive rows with one
date. A held-out page contributes nothing (labels, forms, extractor
statistics) to the model that labels it.
"""

import csv
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


def load(practice=None, lexicon=None):
    practice = practice or os.path.join(ROOT, "data", "practice.csv")
    lexicon = lexicon or os.path.join(ROOT, "data", "lexicon.json")
    with open(practice, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    with open(lexicon, encoding="utf-8") as f:
        lex = json.load(f)
    return rows, lex


def pages(rows):
    """Row id -> page number."""
    out, page, prev = {}, 0, None
    for r in rows:
        if r["date"] != prev:
            page, prev = page + 1, r["date"]
        out[r["id"]] = page
    return out


def page_folds(rows, k=5, seed=0):
    """k lists of row indices; each page falls in exactly one fold."""
    pg = pages(rows)
    ids = sorted(set(pg.values()))
    random.Random(seed).shuffle(ids)
    fold_of = {p: i % k for i, p in enumerate(ids)}
    folds = [[] for _ in range(k)]
    for i, r in enumerate(rows):
        folds[fold_of[pg[r["id"]]]].append(i)
    return folds


def facts(row):
    return json.loads(row["form"]) if row.get("form") else []
