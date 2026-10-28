"""Train and calibrate the label models on a simulation of the run.

The run labels about 18,000 rows with only the 1,900 practice rows as
labelled evidence: about 10% labelled, 90% unlabelled text. The simulation
recreates such ratios inside page-grouped cross-validation:

1. Every row is extracted by an extractor that never saw its fold.
2. For each fold and each ratio (--labelled), that fraction of the other
   pages is labelled evidence; every other row is unlabelled text.
3. Pass 1 labels the fold's rows from that evidence.
4. Pass 2 (self-training) adds what pass 1 is confident about to the
   evidence and labels them again. A row's own page, and copies of its
   sentence, never count for it.

The models are trained on every ratio at once, as the shipped ones are; a
fold's predictions come from models that never saw the fold. A calibration
(Platt scaling) maps the model's P(true) to how often such rows are really
true or false; its error (ECE) is measured cross-fitted, each fold calibrated
on the others.

Saves arena/ml/model.json (pass 1), arena/ml/model_pass2.json (pass 2), each
with its calibration, and eval/calibration_labels.json (the report).

    python3 eval/train_model.py [--no-save] [--model boost|logreg] [--labelled 0.1 0.25 1.0]
"""

import argparse
import json
import os
import random
import sys

from common import ROOT, facts, load, page_folds, pages
from eval_classify import report

from arena.extract import build_extractor, extract_batch
from arena.ml.model import PASS2_PATH, Boost, Calibration, LogReg, decide, featurize
from arena.truth import build_kb, check_fact, page_groups

REPORT_PATH = os.path.join(ROOT, "eval", "calibration_labels.json")
# The regime the calibration is fitted on: all practice is labelled evidence
# in the run, as here every other page is.
CALIBRATE_ON = 1.0


def statements_out_of_fold(rows, lex, folds, oracle=False):
    """What every row states, read by an extractor that never saw its fold."""
    out = [None] * len(rows)
    for test in folds:
        held = set(test)
        order = sorted(test)
        if oracle:
            exs = [{"facts": facts(rows[i]), "complete": True, "issues": [], "scores": []} for i in order]
        else:
            ex = build_extractor([r for i, r in enumerate(rows) if i not in held], lex)
            exs = extract_batch([dict(rows[i], label="") for i in order], lex, ex)
        for i, e in zip(order, exs):
            out[i] = e
    return out


def setups(rows, lex, folds, stmts, labelled, seed=0):
    """Per fold: the labelled base and the unlabelled pool for one ratio."""
    pg = pages(rows)
    unl_rows = [dict(r, label="") for r in rows]
    out = []
    for test in folds:
        held = set(test)
        other = sorted({pg[r["id"]] for i, r in enumerate(rows) if i not in held})
        random.Random(seed).shuffle(other)
        lab = set(other[:max(1, int(len(other) * labelled))])
        is_lab = [i not in held and pg[r["id"]] in lab for i, r in enumerate(rows)]
        kb = build_kb([r for i, r in enumerate(rows) if is_lab[i]], lex)
        pool = [i for i in range(len(rows)) if not is_lab[i]]
        kb.add_statements([unl_rows[i] for i in pool], [stmts[i] for i in pool])
        out.append((test, kb, pool))
    return out


def features(rows, stmts, kb_of_fold, own_page):
    X = [None] * len(rows)
    for test, kb in kb_of_fold:
        for i in test:
            r = dict(rows[i], label="")
            X[i] = featurize(r, stmts[i], [check_fact(f, r["date"], kb, own_page[r["id"]])
                                           for f in stmts[i]["facts"]])
    return X


def out_of_fold_probs(Xs, y, folds, make):
    """For every ratio, each fold predicted by a model trained on the other
    folds of every ratio."""
    Ps = {frac: [None] * len(y) for frac in Xs}
    for test in folds:
        held = set(test)
        trX, trY = [], []
        for X in Xs.values():
            for i in range(len(y)):
                if i not in held:
                    trX.append(X[i])
                    trY.append(y[i])
        m = make().fit(trX, trY)
        for frac, X in Xs.items():
            for i in test:
                Ps[frac][i] = m.probs(X[i])
    return Ps


def ece(y, preds, bins=10):
    """Expected calibration error of firm labels: |accuracy - confidence| by bin."""
    firm = [(t, lab, c) for t, (lab, c) in zip(y, preds) if c is not None]
    total = 0.0
    for b in range(bins):
        lo, hi = 0.5 + b * 0.05, 0.5 + (b + 1) * 0.05
        group = [(t, lab, c) for t, lab, c in firm if lo <= c < hi or (b == bins - 1 and c == 1.0)]
        if group:
            acc = sum(t == lab for t, lab, _ in group) / len(group)
            conf = sum(c for _, _, c in group) / len(group)
            total += len(group) * abs(acc - conf)
    return total / max(1, len(firm))


def cross_fitted(y, P, folds, unsure_below):
    """Calibrated decisions, each fold calibrated on the other folds."""
    out = [None] * len(y)
    for test in folds:
        held = set(test)
        cal = Calibration.fit([P[i]["true"] for i in range(len(y)) if i not in held],
                              [y[i] for i in range(len(y)) if i not in held])
        for i in test:
            out[i] = decide(P[i], unsure_below, cal)
    return out


def reliability(y, preds):
    """Bins of the report: per label and confidence range, rows and accuracy."""
    out = []
    for lab in ("true", "false"):
        for lo, hi in ((0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.0001)):
            g = [(t, c) for t, (l, c) in zip(y, preds) if l == lab and c is not None and lo <= c < hi]
            if g:
                out.append({"label": lab, "from": lo, "to": min(hi, 1.0), "n": len(g),
                            "accuracy": round(sum(t == lab for t, _ in g) / len(g), 3),
                            "confidence": round(sum(c for _, c in g) / len(g), 3)})
    return out


def make_model(kind="boost"):
    return (lambda: Boost(rounds=300, depth=2)) if kind == "boost" else (lambda: LogReg())


def simulate(rows, lex, labelled, tau, make, oracle=False):
    """Out-of-fold features and probabilities of both passes, per ratio."""
    folds = page_folds(rows)
    y = [r["label"] for r in rows]
    own_page = page_groups(rows)
    unl_rows = [dict(r, label="") for r in rows]
    stmts = statements_out_of_fold(rows, lex, folds, oracle)
    sets = {frac: setups(rows, lex, folds, stmts, frac) for frac in labelled}
    X1 = {frac: features(rows, stmts, [(t, kb) for t, kb, _ in s], own_page) for frac, s in sets.items()}
    P1 = out_of_fold_probs(X1, y, folds, make)
    X2 = {}
    for frac, s in sets.items():
        kb2s = [(test, kb.with_pseudo([unl_rows[i] for i in pool], [stmts[i] for i in pool],
                                      [P1[frac][i] for i in pool], tau))
                for test, kb, pool in s]
        X2[frac] = features(rows, stmts, kb2s, own_page)
    P2 = out_of_fold_probs(X2, y, folds, make)
    return folds, X1, X2, P1, P2


def fit_final(y, X1, X2, P1, P2, make):
    """Both passes' models on every ratio, calibrated on CALIBRATE_ON."""
    out = []
    for X, Ps in ((X1, P1), (X2, P2)):
        m = make().fit([x for frac in X for x in X[frac]], y * len(X))
        m.calibration = Calibration.fit([p["true"] for p in Ps[CALIBRATE_ON]], y)
        out.append(m)
    return out


def train(rows, lex, labelled=(0.1, 0.25, 1.0), tau=0.85, kind="boost"):
    """Pass-1 and pass-2 models trained and calibrated on these rows only."""
    labelled = sorted(set(labelled) | {CALIBRATE_ON})
    make = make_model(kind)
    y = [r["label"] for r in rows]
    _, X1, X2, P1, P2 = simulate(rows, lex, labelled, tau, make)
    return fit_final(y, X1, X2, P1, P2, make)


def low_bins(y, preds):
    """Bins of 20+ rows whose accuracy is more than 0.05 below their confidence."""
    return [b for b in reliability(y, preds) if b["n"] >= 20 and b["accuracy"] < b["confidence"] - 0.05]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--oracle", action="store_true", help="gold forms instead of the extractor")
    ap.add_argument("--model", choices=("boost", "logreg"), default="boost")
    ap.add_argument("--labelled", type=float, nargs="+", default=[0.1, 0.25, 1.0],
                    help="fractions of the other pages that are labelled evidence")
    ap.add_argument("--tau", type=float, default=0.85)
    ap.add_argument("--unsure-below", type=float, default=0.0)
    ap.add_argument("--dump", help="write the out-of-fold probabilities to this JSON file")
    args = ap.parse_args()
    if CALIBRATE_ON not in args.labelled:
        args.labelled.append(CALIBRATE_ON)
    make = make_model(args.model)
    rows, lex = load()
    y = [r["label"] for r in rows]
    report([(g, "true") for g in y], "always true")
    folds, X1, X2, P1, P2 = simulate(rows, lex, args.labelled, args.tau, make, args.oracle)

    if args.dump:
        with open(args.dump, "w", encoding="utf-8") as f:
            json.dump({"y": y, "folds": folds, "pass1": {str(k): v for k, v in P1.items()},
                       "pass2": {str(k): v for k, v in P2.items()}}, f)
    summary = {}
    for name, Ps in (("pass1", P1), ("pass2", P2)):
        for frac in args.labelled:
            raw = [decide(p, args.unsure_below) for p in Ps[frac]]
            cal = cross_fitted(y, Ps[frac], folds, args.unsure_below)
            tag = f"{name}, {int(frac * 100)}% of the other pages labelled"
            report([(t, lab) for t, (lab, _) in zip(y, cal)], tag + ", calibrated")
            summary[(name, frac)] = (ece(y, raw), ece(y, cal), raw, cal)
            print(f"ECE: {summary[(name, frac)][0]:.3f} before, {summary[(name, frac)][1]:.3f} after "
                  f"(raw accuracy {sum(t == l for t, (l, _) in zip(y, raw)) / len(y):.3f}); "
                  f"bins of 20+ rows more than 0.05 below their confidence: "
                  f"{len(low_bins(y, raw))} before, {len(low_bins(y, cal))} after")

    if not args.no_save:
        meta = {"rows": len(rows), "oracle": args.oracle, "labelled": args.labelled, "tau": args.tau,
                "trained_on": "simulated runs over data/practice.csv, 5 page-grouped folds",
                "calibrated_on": f"out-of-fold predictions, {int(CALIBRATE_ON * 100)}% labelled"}
        m1, m2 = fit_final(y, X1, X2, P1, P2, make)
        m1.save(meta=dict(meta, passes="1"))
        m2.save(PASS2_PATH, meta=dict(meta, passes="2"))
        before, after, _, cal = summary[("pass2", CALIBRATE_ON)]
        doc = {"method": "platt",
               "fitted_on": "out-of-fold practice, page-grouped 5-fold; pass 2 (label_rows), "
                            f"{int(CALIBRATE_ON * 100)}% of the other pages labelled; "
                            "bins and ECE cross-fitted (each fold calibrated on the others)",
               "rows": len(y),
               "accuracy": round(sum(t == l for t, (l, _) in zip(y, cal)) / len(y), 3),
               "bins": reliability(y, cal),
               "ece_before": round(before, 3), "ece_after": round(after, 3),
               "low_bins_after": len(low_bins(y, cal)),
               "regimes": [{"pass": name, "labelled": frac, "ece_before": round(b, 3),
                            "ece_after": round(a, 3),
                            "accuracy": round(sum(t == l for t, (l, _) in zip(y, c)) / len(y), 3)}
                           for (name, frac), (b, a, _, c) in summary.items()]}
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(doc, f, indent=2)
        print("saved arena/ml/model.json, arena/ml/model_pass2.json and eval/calibration_labels.json")


if __name__ == "__main__":
    sys.exit(main())
