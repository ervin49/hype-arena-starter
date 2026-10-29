import csv
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import synth_universe as S  # noqa: E402

from arena.truth import source_key  # noqa: E402
from arena.values import parse_values  # noqa: E402

ROWS, STATS = S.build()
with open(S.PRACTICE, encoding="utf-8-sig", newline="") as f:
    PRACTICE = list(csv.DictReader(f))
GOLD = {r["id"]: r for r in PRACTICE}


def test_every_practice_row_stays_with_every_fifth_label_hidden():
    by_id = {r["id"]: r for r in ROWS}
    for i, p in enumerate(PRACTICE):
        r = by_id[p["id"]]
        assert r["text"] == p["text"] and r["date"] == p["date"]
        assert r["label"] == ("" if i % 5 == 0 else p["label"])


def test_nine_copies_per_true_row_one_per_false_none_per_unsure():
    n = Counter(r["id"].split(".c")[0] for r in ROWS if ".c" in r["id"])
    for p in PRACTICE:
        assert n.get(p["id"], 0) == {"true": 9, "false": 1}.get(p["label"], 0), p["id"]
    assert STATS["rows"] == len(ROWS) == 16403


def test_copies_keep_the_date_and_the_values_and_change_the_source_key():
    for r in ROWS:
        if ".c" not in r["id"]:
            continue
        src = GOLD[r["id"].split(".c")[0]]
        assert r["label"] == "" and r["date"] == src["date"]
        assert source_key(r["text"]) != source_key(src["text"])
        assert [v["value"] for v in parse_values(r["text"])] == [v["value"] for v in parse_values(src["text"])]


def test_copies_follow_their_row_so_pages_stay_whole():
    from arena.truth import page_groups
    pages = page_groups(ROWS)
    for r in ROWS:
        if ".c" in r["id"]:
            assert r["id"].split(".c")[0] in pages[r["id"]]
    plain, _ = S.build(copies={})
    assert [r["id"] for r in plain] == [p["id"] for p in PRACTICE]
    assert len({id(v) for v in page_groups(ROWS).values()}) == len({id(v) for v in page_groups(plain).values()})


def test_number_format_never_makes_a_year():
    assert S.number_variants("Hooly has 2,048 customers.") == []
    assert S.number_variants("Hooly has 2,600 customers.") == ["Hooly has 2600 customers."]
    assert S.number_variants("It holds 31,000,000,000 images.") == ["It holds 31000000000 images."]
