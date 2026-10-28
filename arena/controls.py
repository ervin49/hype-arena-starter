"""Controls: checks the run makes on its own input, so that its confidence holds there too.

- Confidence control. A fixed control group of practice pages was left out of the control
  model's training (scripts/train_control.py). In the run, the control model labels those rows
  as if unknown, in the context of the real input, and we compare what it said with their labels.
  Each answer's confidence c becomes 0.5 + k (c - 0.5), with k in [0, 1] fitted per label on the
  control group (least Brier score). Confidence is only ever lowered; labels never change.
- Distribution monitor: the share of `false` answers on the input against the control group.
- Claim control: the rows the engine is confident about are evidence that can veto a claim
  (arena.generate.select_claims, check_rows).
"""
import json
import os

from arena.ml.model import load_model

CONTROL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "control")
CONTROL_FOLDS, CONTROL_FOLD, CONTROL_SEED = 5, 0, 0
MIN_CONTROL = 100      # fewer control answers than this: no adjustment
MIN_PER_LABEL = 30     # fewer answers of one label than this: that label uses the pooled factor
CHECK_CONFIDENCE = 0.9  # rows labelled true at least this sure can veto a claim


def load_control(path=CONTROL_DIR):
    """(control ids, pass-1 model, pass-2 model), or None without the files."""
    try:
        with open(os.path.join(path, "ids.json"), encoding="utf-8") as f:
            ids = set(json.load(f)["ids"])
        m1, m2 = load_model(os.path.join(path, "model.json")), load_model(os.path.join(path, "model_pass2.json"))
    except (OSError, ValueError, KeyError):
        return None
    return (ids, m1, m2) if ids and m1 else None


def shrink(c, k):
    return round(min(1.0, max(0.5, 0.5 + k * (c - 0.5))), 3)


def fit_factor(answers):
    """k in [0, 1] (steps of 0.02) with the least Brier score of the shrunk confidences.
    answers: [(confidence, right)]."""
    def brier(k):
        return sum((shrink(c, k) - right) ** 2 for c, right in answers)
    return min((i / 50 for i in range(51)), key=lambda k: (brier(k), -k))


def ece(answers, bins=5):
    total, n = 0.0, len(answers)
    for b in range(bins):
        lo, hi = 0.5 + b * 0.5 / bins, 0.5 + (b + 1) * 0.5 / bins
        xs = [(c, r) for c, r in answers if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if xs:
            total += len(xs) / n * abs(sum(c for c, _ in xs) / len(xs) - sum(r for _, r in xs) / len(xs))
    return round(total, 3) if n else None


def measure(control_predictions, truth):
    """The factors from the control group's answers. control_predictions: [{id, label, confidence}];
    truth: {id: label}. Rows whose true label is unsure, or answered unsure, are left out."""
    answers = {"true": [], "false": []}
    for p in control_predictions:
        gold, label, c = truth.get(p["id"]), p.get("label"), p.get("confidence")
        if gold in ("true", "false") and label in answers and c is not None:
            answers[label].append((float(c), 1.0 if label == gold else 0.0))
    pooled = answers["true"] + answers["false"]
    report = {"control_answers": len(pooled)}
    if len(pooled) < MIN_CONTROL:
        return {"true": 1.0, "false": 1.0}, dict(report, note="too few control answers: no adjustment")
    k_all = fit_factor(pooled)
    factors = {lab: fit_factor(a) if len(a) >= MIN_PER_LABEL else k_all for lab, a in answers.items()}
    after = [(shrink(c, factors[lab]), r) for lab, a in answers.items() for c, r in a]
    report.update(accuracy=round(sum(r for _, r in pooled) / len(pooled), 3),
                  ece_before=ece(pooled), ece_after=ece(after),
                  said=round(sum(c for c, _ in pooled) / len(pooled), 3),
                  said_after=round(sum(c for c, _ in after) / len(after), 3),
                  false_share=round(len(answers["false"]) / len(pooled), 3),
                  factors=factors, per_label={lab: len(a) for lab, a in answers.items()})
    return factors, report


def apply(predictions, factors):
    """Lower each answer's confidence by its label's factor, in place."""
    for p in predictions.values():
        k = factors.get(p.get("label"))
        if k is not None and p.get("confidence") is not None:
            p["confidence"] = shrink(float(p["confidence"]), k)


def control_input(rows, practice, control_ids):
    """The input with the control group's labels hidden, and the practice without it."""
    hidden = [{**r, "label": ""} if r["id"] in control_ids and r["label"] else r for r in rows]
    shown = {r["id"] for r in rows if r["label"]}
    group = [r["id"] for r in rows if r["id"] in control_ids and r["label"]]
    return hidden, [r for r in practice if r["id"] not in control_ids], group, shown


def check_rows(rows, batch):
    """Input rows the engine labelled true with at least CHECK_CONFIDENCE, with the facts it
    read from them (complete extractions only), in the shape of practice rows."""
    by_id = {r["id"]: r for r in rows}
    out = []
    for p in batch:
        ex = p.get("extraction") or {}
        r = by_id.get(p.get("id"))
        if (r is None or p.get("label") != "true" or (p.get("confidence") or 0) < CHECK_CONFIDENCE
                or not ex.get("complete") or not ex.get("facts")):
            continue
        out.append({"id": r["id"], "text": r["text"], "date": r["date"], "label": "true",
                    "form": json.dumps(ex["facts"])})
    return out
