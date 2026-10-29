"""The ensemble against the single model, on rows neither was trained on.

Each split cuts the practice data into known rows (labelled) and unseen rows
(labels hidden): the 5 page folds (out of fold), and the shift test's three
scenarios (scripts/shift_test.py). On the known rows only, we train the
single model pair (train_model.train) and an ensemble of 5 pairs, each without
one page fold of the known rows, as eval/train_ensemble.py does on all of
practice. Both label the unseen rows with label_rows; we compare accuracy,
false caught, ECE, Brier and log loss, and the ensemble's mean spread on right
and wrong answers. The trainings run in parallel (about 15 minutes).

    python3 eval/eval_ensemble.py [--splits folds random latest subjects]
"""

import argparse
import json
import math
import os
import sys
from multiprocessing import Pool

from common import ROOT, load, page_folds
from train_model import ece, train

sys.path.insert(0, os.path.join(ROOT, "scripts"))
import shift_test  # noqa: E402

from arena.classify import label_rows  # noqa: E402
from arena.ml.model import Ensemble  # noqa: E402

K = 5
OUT = os.path.join(ROOT, "eval", "ensemble_report.json")


def masks(rows, names):
    """name -> [known?] per row."""
    out = {}
    if "folds" in names:
        for f, test in enumerate(page_folds(rows, K, seed=0)):
            held = set(test)
            out[f"fold {f}"] = [i not in held for i in range(len(rows))]
    for name, split in (("random", shift_test.split_random), ("latest", shift_test.split_time),
                        ("subjects", shift_test.split_subjects)):
        if name in names:
            out[name] = split(rows)
    return out


def fit(job):
    """(split, member): member None is the single model, else the ensemble
    member trained without that page fold of the known rows."""
    split, member, mask = job
    rows, lex = load()
    known = [r for r, k in zip(rows, mask) if k]
    if member is not None:
        held = set(page_folds(known, K, seed=0)[member])
        known = [r for i, r in enumerate(known) if i not in held]
    return split, member, train(known, lex)


def p_true(p):
    return p["confidence"] if p["label"] == "true" else 1 - p["confidence"]


def score(preds, gold):
    ans = [(p, gold[p["id"]]) for p in preds
           if gold[p["id"]] in ("true", "false") and p["label"] != "unsure"]
    y = [g for _, g in ans]
    n = len(ans)
    right = [p["label"] == g for p, g in ans]
    pt = [min(max(p_true(p), 1e-6), 1 - 1e-6) for p, _ in ans]
    out = {"n": n, "accuracy": round(sum(right) / n, 4),
           "always_true": round(sum(g == "true" for g in y) / n, 4),
           "false_caught": sum(p["label"] == g == "false" for p, g in ans),
           "false_rows": sum(g == "false" for g in y),
           "false_called": sum(p["label"] == "false" for p, _ in ans),
           "ece": round(ece(y, [(p["label"], p["confidence"]) for p, _ in ans]), 4),
           "brier": round(sum((q - (g == "true")) ** 2 for q, g in zip(pt, y)) / n, 4),
           "log_loss": round(-sum(math.log(q if g == "true" else 1 - q) for q, g in zip(pt, y)) / n, 4)}
    if all("spread" in p for p, _ in ans):
        sr = [p["spread"] for (p, _), r in zip(ans, right) if r]
        sw = [p["spread"] for (p, _), r in zip(ans, right) if not r]
        out["spread_right"] = round(sum(sr) / max(1, len(sr)), 4)
        out["spread_wrong"] = round(sum(sw) / max(1, len(sw)), 4)
        out["spread_all"] = [round(p["spread"], 4) for p, _ in ans]
        out["right_all"] = right
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--splits", nargs="+", default=["folds", "random", "latest", "subjects"])
    args = ap.parse_args()
    rows, lex = load()
    gold = {r["id"]: r["label"] for r in rows}
    ms = masks(rows, args.splits)
    jobs = [(name, member, mask) for name, mask in ms.items() for member in [None] + list(range(K))]
    models = {}
    with Pool(min(len(jobs), os.cpu_count() or 4)) as pool:
        for name, member, pair in pool.imap_unordered(fit, jobs):
            models[(name, member)] = pair
            print(f"trained {name}, {'single' if member is None else f'member {member}'} "
                  f"({len(models)}/{len(jobs)})", flush=True)

    preds = {}
    for name, mask in ms.items():
        run_input = [r if k else {**r, "label": ""} for r, k in zip(rows, mask)]
        known = [r for r, k in zip(rows, mask) if k]
        ens = (Ensemble([models[(name, m)][0] for m in range(K)]),
               Ensemble([models[(name, m)][1] for m in range(K)]))
        preds[name] = {"single": label_rows(run_input, known, lex, models=models[(name, None)]),
                       "ensemble": label_rows(run_input, known, lex, models=ens)}

    report = {}
    groups = {"out of fold": [n for n in ms if n.startswith("fold")]}
    groups.update({n: [n] for n in ms if not n.startswith("fold")})
    for group, names in groups.items():
        if not names:
            continue
        report[group] = {kind: score([p for n in names for p in preds[n][kind]], gold)
                         for kind in ("single", "ensemble")}
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(report, f)
    print(f"\n{'split':12} {'model':9} {'n':>5} {'right':>6} {'always':>6} {'lies':>9} {'called':>6} "
          f"{'ECE':>6} {'Brier':>7} {'logloss':>7}  spread right / wrong")
    for group, r in report.items():
        for kind, s in r.items():
            sp = f"{s['spread_right']:.3f} / {s['spread_wrong']:.3f}" if "spread_right" in s else ""
            print(f"{group:12} {kind:9} {s['n']:5} {s['accuracy']:6.3f} {s['always_true']:6.3f} "
                  f"{s['false_caught']:4}/{s['false_rows']:<4} {s['false_called']:6} {s['ece']:6.3f} "
                  f"{s['brier']:7.4f} {s['log_loss']:7.4f}  {sp}")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
