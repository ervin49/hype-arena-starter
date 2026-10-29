"""Train and measure layer 3, the confidence model (arena/confidence.py).

1. Out-of-fold answers: for each of 5 page folds, A's models are trained without it
   (eval/train_model.train) and label it, the other folds labelled as in the run. Each
   answer is kept with whether it was right. Cached in reports/confidence_oof.json.
2. Honest measure (nested): the confidence model is trained on 4 folds of those answers and
   applied to the 5th, for every fold; compared with the engine alone on the same answers.
3. The final model, trained on all the answers: reports/confidence_model.json, with the
   measure in its meta, and the comparison in reports/confidence_layer.json. Not used by the
   run: under shift it is over-confident (scripts/shift_test.py --layer3).

    .venv/bin/python scripts/train_confidence.py            # uses the cache if present
    .venv/bin/python scripts/train_confidence.py --rebuild  # retrains the 5 fold models (~7 min)
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from common import load, page_folds  # noqa: E402

from arena import confidence  # noqa: E402
from arena.controls import ece  # noqa: E402

CACHE = os.path.join(ROOT, "reports", "confidence_oof.json")
REPORT = os.path.join(ROOT, "reports", "confidence_layer.json")
FOLDS, SEED = 5, 0


def out_of_fold(rows, lex):
    from train_model import train
    from arena.classify import label_rows
    out = []
    for k, fold in enumerate(page_folds(rows, FOLDS, seed=SEED)):
        held = set(fold)
        known = [r for i, r in enumerate(rows) if i not in held]
        run_input = [{**r, "label": ""} if i in held else r for i, r in enumerate(rows)]
        print(f"fold {k}: training on {len(known)} rows, labelling {len(held)}", flush=True)
        preds = label_rows(run_input, known, lex, models=train(known, lex))
        gold = {rows[i]["id"]: rows[i]["label"] for i in held}
        for p in preds:
            if p["id"] in gold:
                p.pop("reason", None)
                out.append({"fold": k, "gold": gold[p["id"]], "prediction": p})
    return out


def measure(answers):
    """Accuracy, lies caught, ECE and Brier of (label, confidence, gold) answers, decided ones only."""
    a = [(lab, c, g) for lab, c, g in answers if g in ("true", "false") and lab in ("true", "false") and c is not None]
    pairs = [(float(c), 1.0 if lab == g else 0.0) for lab, c, g in a]
    n = len(pairs)
    return {"n": n, "accuracy": round(sum(r for _, r in pairs) / n, 4),
            "lies_caught": sum(1 for lab, _, g in a if g == "false" and lab == "false"),
            "lies": sum(1 for _, _, g in a if g == "false"),
            "false_answers": sum(1 for lab, _, _ in a if lab == "false"),
            "ece": ece(pairs), "brier": round(sum((c - r) ** 2 for c, r in pairs) / n, 4),
            "said": round(sum(c for c, _ in pairs) / n, 3)}


def trainable(records):
    X, y = [], []
    for r in records:
        p = r["prediction"]
        if r["gold"] in ("true", "false") and p.get("label") in ("true", "false"):
            X.append(confidence.features(p))
            y.append(1.0 if p["label"] == r["gold"] else 0.0)
    return X, y


def nested(records, l2):
    """Every answer judged by a confidence model trained without its fold."""
    answers = []
    for k in range(FOLDS):
        model = confidence.ConfidenceModel().fit(*trainable([r for r in records if r["fold"] != k]), l2=l2)
        for r in records:
            if r["fold"] == k:
                label, conf, _ = confidence.decide(dict(r["prediction"]), model)
                answers.append((label, conf, r["gold"]))
    return answers


def main():
    rows, lex = load()
    if "--rebuild" in sys.argv or not os.path.exists(CACHE):
        records = out_of_fold(rows, lex)
        with open(CACHE, "w", encoding="utf-8") as f:
            json.dump(records, f)
    with open(CACHE, encoding="utf-8") as f:
        records = json.load(f)

    engine = measure([(r["prediction"]["label"], r["prediction"]["confidence"], r["gold"]) for r in records])
    print(f"engine alone          {engine}")
    best = None
    for l2 in (0.3, 1.0, 3.0, 10.0):
        m = measure(nested(records, l2))
        print(f"confidence model l2={l2:<4} {m}")
        if best is None or m["brier"] < best[1]["brier"]:
            best = (l2, m)
    l2, layer = best
    model = confidence.ConfidenceModel(meta={"l2": l2, "trained_on": f"{len(records)} out-of-fold answers",
                                             "engine": engine, "nested": layer})
    model.fit(*trainable(records), l2=l2)
    model.save()
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump({"measured_on": "out-of-fold answers on all practice rows; the confidence model "
                                  "trained without each answer's fold (nested)",
                   "l2": l2, "engine": engine, "confidence_model": layer}, f, indent=1)
        f.write("\n")
    print(f"chose l2={l2}; wrote {os.path.relpath(confidence.MODEL_PATH, ROOT)} and {os.path.relpath(REPORT, ROOT)}")
    top = sorted(model.w.items(), key=lambda kv: -abs(kv[1]))[:12]
    print("strongest signs:", ", ".join(f"{k} {v:+.2f}" for k, v in top))


if __name__ == "__main__":
    main()
