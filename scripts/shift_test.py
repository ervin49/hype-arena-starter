"""Does the confidence control hold when the run's rows differ from the practice rows?

Each scenario splits the practice data into "known" rows (labelled, as the practice rows are
in the run) and "unseen" rows (labels hidden, as the ~18,000 are). Nothing is learned from the
unseen rows: the main model and the control model are trained on the known rows only
(eval/train_model.py), the control group being a fold of the known pages. Then, as in the run:
the main model labels the unseen rows, the control model labels the control group, and
arena.controls lowers the confidence as far as the control group shows. We compare what we
said with how often we were right on the unseen rows, before and after the control.

With --layer3, layer 3, the confidence model (arena/confidence.py), is trained in each scenario on the known
rows only: on out-of-fold answers of 5 page folds of them, as scripts/train_confidence.py does
on all practice. It is measured on the unseen rows with and without its flip rule.

Scenarios: random pages (no shift), the latest pages (time shift), the rows of held-out
subjects (subject shift). Takes about 8 minutes, 35 with --layer3. Writes reports/shift_test.json
(reports/shift_test_layer3.json with --layer3).

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

from arena import confidence, controls  # noqa: E402
from arena.classify import label_rows  # noqa: E402

UNSEEN_SHARE = 0.2
OUT = os.path.join(ROOT, "reports", "shift_test_layer3.json" if "--layer3" in sys.argv else "shift_test.json")


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


def layer3_on_known(known, lex, run_input, known_ids):
    """The confidence model trained on out-of-fold answers of the known rows only."""
    X, y = [], []
    for k, fold in enumerate(page_folds(known, 5, seed=0)):
        held = {known[i]["id"] for i in fold}
        rest = [r for r in known if r["id"] not in held]
        inp = [{**r, "label": ""} if r["id"] in held else r for r in run_input]
        print(f"   layer 3 fold {k}: training on {len(rest)}", flush=True)
        gold = {r["id"]: r["label"] for r in known if r["id"] in held}
        for p in label_rows(inp, rest, lex, models=train(rest, lex)):
            g = gold.get(p["id"])
            if g in ("true", "false") and p.get("label") in ("true", "false"):
                X.append(confidence.features(p))
                y.append(1.0 if p["label"] == g else 0.0)
    return confidence.ConfidenceModel().fit(X, y, l2=confidence.L2)


def with_layer3(preds, model, truth, flip, control=None):
    """Layer 3 on the unseen rows' answers; with control = (control answers, their truth), the
    run-time control is then fitted on the control group passed through layer 3 too, and applied."""
    saved = confidence.FLIP_BELOW
    confidence.FLIP_BELOW = flip
    try:
        out = [dict(p) for p in preds]
        confidence.apply(out, model)
        if control:
            ctrl = [dict(p) for p in control[0]]
            confidence.apply(ctrl, model)
            factors, _ = controls.measure(ctrl, control[1])
            controls.apply({p["id"]: p for p in out}, factors)
    finally:
        confidence.FLIP_BELOW = saved
    ans = answers(out, truth)
    return dict(summary(ans), lies_caught=sum(1 for p in out if truth.get(p["id"]) == "false" and p["label"] == "false"),
                lies=sum(1 for g in truth.values() if g == "false"))


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
    lies = sum(1 for g in truth.values() if g == "false")
    result["unseen_before"]["lies_caught"] = sum(1 for p in preds if truth.get(p["id"]) == "false" and p["label"] == "false")
    result["unseen_before"]["lies"] = lies
    result["unseen_after"]["lies_caught"] = sum(1 for p in after_preds.values()
                                                if truth.get(p["id"]) == "false" and p["label"] == "false")
    result["unseen_after"]["lies"] = lies
    if "--layer3" not in sys.argv:
        print(json.dumps(result), flush=True)
        return result
    print(f"[{name}] layer 3 on the known rows", flush=True)
    model = layer3_on_known(known, lex, run_input, {r["id"] for r in known})
    lies = sum(1 for g in truth.values() if g == "false")
    result["unseen_before"]["lies_caught"] = sum(1 for p in preds if truth.get(p["id"]) == "false" and p["label"] == "false")
    result["unseen_before"]["lies"] = lies
    control = ([p for p in ctrl_preds if p["id"] in group], {r["id"]: r["label"] for r in known if r["id"] in group})
    result["layer3_no_flip"] = with_layer3(preds, model, truth, 0.0)
    result["layer3_flip"] = with_layer3(preds, model, truth, 0.5)
    result["layer3_no_flip_control"] = with_layer3(preds, model, truth, 0.0, control)
    result["layer3_flip_control"] = with_layer3(preds, model, truth, 0.5, control)
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
    if "--layer3" not in sys.argv:
        print(f"wrote {os.path.relpath(OUT, ROOT)}")
        return
    print(f"\n{'scenario':18} {'engine + control':>26} {'+ layer 3 + control':>26} {'+ layer 3 flip + control':>26}"
          "   (right / lies / ECE)")
    for r in results:
        cells = [r["unseen_after"], r["layer3_no_flip_control"], r["layer3_flip_control"]]
        print(f"{r['scenario']:18} " + " ".join(f"{c['right']:.3f} {c['lies_caught']:3}/{c['lies']:<3} {c['ece']:.3f}".rjust(26) for c in cells))
    print(f"wrote {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
