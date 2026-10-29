import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "eval"))

from augment import MIX, augment, stated, timelines  # noqa: E402
from common import load  # noqa: E402

from arena.values import compatible  # noqa: E402

ROWS, LEX = load()
SYNTH = augment(ROWS, LEX, 277)
BY_ID = {r["id"]: r for r in ROWS}


def test_mix_follows_the_real_lies():
    got = Counter(s["lie"] for s in SYNTH)
    assert len(SYNTH) == 277
    for lie, n in MIX.items():
        assert abs(got[lie] / len(SYNTH) - n / sum(MIX.values())) < 0.03, got


def test_one_fact_changed_and_the_text_states_it():
    aliases = {}
    for s in SYNTH:
        src = BY_ID[s["source"]]
        assert s["label"] == "false" and s["date"] == src["date"] and s["text"] != src["text"]
        old, new = json.loads(src["form"]), json.loads(s["form"])
        changed = [i for i, (a, b) in enumerate(zip(old, new)) if a != b]
        assert len(old) == len(new) and len(changed) == 1, s
        i = changed[0]
        assert stated(s["text"], new[i]["value"], aliases), s
        assert not stated(s["text"], old[i]["value"], aliases), s


def test_wrong_values_were_never_true_and_stale_ones_were():
    tl = timelines(ROWS)
    for s in SYNTH:
        src = BY_ID[s["source"]]
        old, new = json.loads(src["form"]), json.loads(s["form"])
        f = next(b for a, b in zip(old, new) if a != b)
        hist = tl[(f["subject"], f["attribute"])]
        ever = [d for d, v in hist if compatible(v, f["value"])]
        if s["lie"] == "wrong":
            assert not ever, s
        elif s["lie"] == "stale":
            assert ever and max(ever) < s["date"], s
        else:
            assert ever and min(ever) > s["date"], s
