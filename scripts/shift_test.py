"""Does the confidence control hold when the run's rows differ from the practice rows?

Each scenario splits the practice data into "known" rows (labelled, as the practice rows are
in the run) and "unseen" rows (labels hidden, as the ~18,000 are). Nothing is learned from the
unseen rows: the main model and the control model are trained on the known rows only
(eval/train_model.py), the control group being a fold of the known pages. Then, as in the run:
the main model labels the unseen rows, the control model labels the control group, and
arena.controls lowers the confidence as far as the control group shows. We compare what we
said with how often we were right on the unseen rows, before and after the control.

Scenarios: random pages (no shift), the latest pages (time shift), the rows of held-out
subjects (subject shift). Takes about 8 minutes. Writes reports/shift_test.json.

    .venv/bin/python scripts/shift_test.py
"""
import json
import os
import random
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from common import load, page_folds, pages  # noqa: E402
from train_model import train  # noqa: E402

from arena import controls  # noqa: E402
from arena.classify import label_rows  # noqa: E402

UNSEEN_SHARE = 0.2
OUT = os.path.join(ROOT, "reports", "shift_test.json")


def split_random(rows):
    held = set(page_folds(rows, 5, seed=1)[0])
    return [i not in held for i in range(len(rows))]


def split_time(rows):
    pg = pages(rows)
    last = sorted(set(pg.values()), key=lambda p: min(r["date"] for r in rows if pg[r["id"]] == p))
    cut = set(last[int(len(last) * (1 - UNSEEN_SHARE)):])
    return [pg[r["id"]] not in cut for r in rows]


def split_subjects(rows):
    subjects = sorted({f["subject"] for r in rows for f in json.loads(r["form"])})
    random.Random(2).shuffle(subjects)
    held, unseen = set(), set()
    for s in subjects:
        if len(unseen) >= UNSEEN_SHARE * len(rows):
            break
        held.add(s)
        unseen |= {r["id"] for r in rows if any(f["subject"] == s for f in json.loads(r["form"]))}
    return [r["id"] not in unseen for r in rows]


def answers(preds, truth):
    out = []
    for p in preds:
        gold = truth.get(p["id"])
        if gold in ("true", "false") and p.get("label") in ("true", "false") and p.get("confidence") is not None:
            out.append((float(p["confidence"]), 1.0 if p["label"] == gold else 0.0, p["label"], p.get("kind")))
    return out


def summary(ans):
    pairs = [(c, r) for c, r, _, _ in ans]
    n = len(pairs)
    return {"n": n, "said": round(sum(c for c, _ in pairs) / n, 3), "right": round(sum(r for _, r in pairs) / n, 3),
            "ece": controls.ece(pairs), "brier": round(sum((c - r) ** 2 for c, r in pairs) / n, 4),
            "unknown_share": round(sum(k == "unknown" for *_, k in ans) / n, 3)}


def scenario(name, rows, lex, known_mask):
    known = [r for r, k in zip(rows, known_mask) if k]
    unseen = [r for r, k in zip(rows, known_mask) if not k]
    truth = {r["id"]: r["label"] for r in unseen}
    run_input = [r if k else {**r, "label": ""} for r, k in zip(rows, known_mask)]
    print(f"[{name}] known {len(known)}, unseen {len(unseen)}: training the main model", flush=True)
    main = train(known, lex)
    preds = label_rows(run_input, known, lex, models=main)

    held = set(page_folds(known, 5, seed=0)[0])
    group = {r["id"] for i, r in enumerate(known) if i in held}
    print(f"[{name}] control group {len(group)}: training the control model", flush=True)
    ctrl = train([r for r in known if r["id"] not in group], lex)
    hidden, known_out, _, _ = controls.control_input(run_input, known, group)
    ctrl_preds = label_rows(hidden, known_out, lex, models=ctrl)
    factors, report = controls.measure([p for p in ctrl_preds if p["id"] in group],
                                       {r["id"]: r["label"] for r in known if r["id"] in group})

    before = answers(preds, truth)
    after_preds = {p["id"]: dict(p) for p in preds}
    controls.apply(after_preds, factors)
    after = answers(after_preds.values(), truth)
    decided = [lab for lab in truth.values() if lab in ("true", "false")]
    result = {"scenario": name, "known": len(known), "unseen": len(unseen),
              "always_true": round(sum(lab == "true" for lab in decided) / len(decided), 3), "factors": factors,
              "control": {k: report.get(k) for k in ("control_answers", "accuracy", "said", "ece_before", "false_share")},
              "control_unknown_share": round(sum(p.get("kind") == "unknown" for p in ctrl_preds if p["id"] in group)
                                             / max(1, len(group)), 3),
              "unseen_before": summary(before), "unseen_after": summary(after)}
    print(json.dumps(result), flush=True)
    return result


def main():
    rows, lex = load()
    results = [scenario(name, rows, lex, split(rows)) for name, split in
               (("random pages", split_random), ("latest pages", split_time), ("held-out subjects", split_subjects))]
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=1)
        f.write("\n")
    print(f"\n{'scenario':18} {'unseen':>6} {'right':>6} {'always':>6} {'said':>6} {'→ after':>7} {'ECE':>6} {'→ after':>7} {'Brier':>7} {'→ after':>7}  factors")
    for r in results:
        b, a = r["unseen_before"], r["unseen_after"]
        print(f"{r['scenario']:18} {b['n']:6} {b['right']:6.3f} {r['always_true']:6.3f} {b['said']:6.3f} {a['said']:7.3f} {b['ece']:6.3f} {a['ece']:7.3f} "
              f"{b['brier']:7.4f} {a['brier']:7.4f}  {r['factors']}")
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
