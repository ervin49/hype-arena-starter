"""Train the label model on out-of-fold features and measure it.

1. For each page-grouped fold, build the base and the extractor from the
   other folds, extract the fold's rows from their text and check them:
   out-of-fold features that look like the run's.
2. Measure the model with the same folds (it never sees a fold's features
   while labelling that fold), next to the rules and to "always true".
3. Fit on every out-of-fold feature and save arena/ml/model.json.

    python3 eval/train_model.py [--no-save] [--l2 1.0]
"""

import argparse
import sys
from collections import Counter

from common import facts, load, page_folds
from eval_classify import report

from arena.classify import classify_rules
from arena.extract import build_extractor, extract_batch
from arena.ml.model import LogReg, decide, featurize
from arena.truth import build_kb, check_fact


def out_of_fold(rows, lex, folds, oracle=False):
    feats, labels, fold_of, rule = [None] * len(rows), [None] * len(rows), [None] * len(rows), [None] * len(rows)
    # what every row states, label unknown, as the run sees the universe
    # (read by an extractor that did not train on the row's page)
    statements = [None] * len(rows)
    for test in folds:
        held = set(test)
        ex_ = build_extractor([r for i, r in enumerate(rows) if i not in held], lex)
        order = sorted(test)
        for i, e in zip(order, extract_batch([dict(rows[i], label="") for i in order], lex, ex_)):
            statements[i] = facts(rows[i]) if oracle else e
            if oracle:
                statements[i] = {"facts": statements[i]}
    unl_rows = [dict(r, label="") for r in rows]
    for fi, test in enumerate(folds):
        held = set(test)
        train = [r for i, r in enumerate(rows) if i not in held]
        kb = build_kb(train, lex)
        kb.add_statements(unl_rows, statements)
        order = sorted(test)
        test_rows = [dict(rows[i], label="") for i in order]
        if oracle:
            exs = [{"facts": facts(r), "complete": True, "issues": [], "scores": []} for r in test_rows]
        else:
            exs = extract_batch(test_rows, lex, build_extractor(train, lex))
        for i, r, ex in zip(order, test_rows, exs):
            checks = [check_fact(f, r["date"], kb) for f in ex["facts"]]
            feats[i] = featurize(r, ex, checks)
            labels[i] = rows[i]["label"]
            fold_of[i] = fi
            rule[i] = classify_rules(r, ex, lambda f, d: check_fact(f, d, kb))["label"]
    return feats, labels, fold_of, rule


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--l2", type=float, default=1.0)
    ap.add_argument("--unsure-below", type=float, default=0.0)
    args = ap.parse_args()
    rows, lex = load()
    folds = page_folds(rows)
    X, y, fold_of, rule = out_of_fold(rows, lex, folds, args.oracle)
    report([(g, "true") for g in y], "always true")
    report(list(zip(y, rule)), "rules")
    preds, confs = [], []
    for fi in range(len(folds)):
        tr = [i for i in range(len(rows)) if fold_of[i] != fi]
        m = LogReg(l2=args.l2).fit([X[i] for i in tr], [y[i] for i in tr])
        for i in range(len(rows)):
            if fold_of[i] == fi:
                lab, c = decide(m.probs(X[i]), args.unsure_below)
                preds.append((i, lab, c))
    preds.sort()
    report([(y[i], lab) for i, lab, _ in preds], "model")
    # confidence buckets: is a 0.8 right 80% of the time?
    buckets = Counter()
    for i, lab, c in preds:
        if c is not None:
            b = min(9, int(c * 10)) / 10
            buckets[(b, "n")] += 1
            buckets[(b, "right")] += y[i] == lab
    print("calibration (confidence bucket: rows, right):")
    for b in sorted({b for b, _ in buckets}):
        n = buckets[(b, "n")]
        print(f"  {b:.1f}+: {n:>5}  {buckets[(b, 'right')] / n:.3f}")
    if not args.no_save:
        m = LogReg(l2=args.l2).fit(X, y)
        m.save(meta={"rows": len(rows), "oracle": args.oracle,
                     "trained_on": "out-of-fold features of data/practice.csv, 5 page-grouped folds"})
        print("saved arena/ml/model.json")


if __name__ == "__main__":
    sys.exit(main())
