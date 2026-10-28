"""Train the label models on a simulation of the run, and measure them.

The run labels about 18,000 rows with only the 1,900 practice rows as
labelled evidence: about 10% labelled, 90% unlabelled text. The simulation
recreates that ratio inside page-grouped cross-validation:

1. Every row is extracted by an extractor that never saw its fold.
2. For each fold, a fraction (--labelled) of the other pages is labelled
   evidence; every other row, the fold's own included, is unlabelled text.
3. Pass 1 labels the fold's rows from that evidence.
4. Pass 2 (self-training) adds what pass 1 is confident about to the
   evidence and labels them again, leaving out each row's own page.

Each pass's model is measured on folds it never trained on, then fitted on
every fold and saved: arena/ml/model.json (pass 1) and model_pass2.json.

    python3 eval/train_model.py [--no-save] [--model boost|logreg] [--labelled 0.1 0.25]
"""

import argparse
import random
import sys
from collections import Counter

from common import facts, load, page_folds, pages
from eval_classify import report

from arena.extract import build_extractor, extract_batch
from arena.ml.model import PASS2_PATH, Boost, LogReg, decide, featurize
from arena.truth import build_kb, check_fact, page_groups


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


def out_of_fold_probs(X, y, folds, make):
    P = [None] * len(X)
    for test in folds:
        held = set(test)
        tr = [i for i in range(len(X)) if i not in held]
        m = make().fit([X[i] for i in tr], [y[i] for i in tr])
        for i in test:
            P[i] = m.probs(X[i])
    return P


def simulate(rows, lex, folds, stmts, labelled, make, tau, seed=0):
    """Pass-1 and pass-2 features and out-of-fold probabilities for one ratio."""
    pg = pages(rows)
    own_page = page_groups(rows)
    y = [r["label"] for r in rows]
    unl_rows = [dict(r, label="") for r in rows]
    X1, setups = [None] * len(rows), []
    for test in folds:
        held = set(test)
        other = sorted({pg[r["id"]] for i, r in enumerate(rows) if i not in held})
        random.Random(seed).shuffle(other)
        lab = set(other[:max(1, int(len(other) * labelled))])
        is_lab = [i not in held and pg[r["id"]] in lab for i, r in enumerate(rows)]
        kb = build_kb([r for i, r in enumerate(rows) if is_lab[i]], lex)
        pool = [i for i in range(len(rows)) if not is_lab[i]]
        kb.add_statements([unl_rows[i] for i in pool], [stmts[i] for i in pool])
        for i in test:
            r = unl_rows[i]
            X1[i] = featurize(r, stmts[i], [check_fact(f, r["date"], kb) for f in stmts[i]["facts"]])
        setups.append((test, kb, pool))
    P1 = out_of_fold_probs(X1, y, folds, make)
    X2 = [None] * len(rows)
    for test, kb, pool in setups:
        kb2 = kb.with_pseudo([unl_rows[i] for i in pool], [stmts[i] for i in pool],
                             [P1[i] for i in pool], tau)
        for i in test:
            r = unl_rows[i]
            X2[i] = featurize(r, stmts[i], [check_fact(f, r["date"], kb2, own_page[r["id"]])
                                            for f in stmts[i]["facts"]])
    P2 = out_of_fold_probs(X2, y, folds, make)
    return X1, X2, P1, P2


def calibration(y, preds):
    buckets = Counter()
    for t, (lab, c) in zip(y, preds):
        if c is not None:
            b = min(9, int(c * 10)) / 10
            buckets[(b, "n")] += 1
            buckets[(b, "right")] += t == lab
    print("calibration (confidence bucket: rows, right):")
    for b in sorted({b for b, _ in buckets}):
        n = buckets[(b, "n")]
        print(f"  {b:.1f}+: {n:>5}  {buckets[(b, 'right')] / n:.3f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-save", action="store_true")
    ap.add_argument("--oracle", action="store_true", help="gold forms instead of the extractor")
    ap.add_argument("--model", choices=("boost", "logreg"), default="boost")
    ap.add_argument("--labelled", type=float, nargs="+", default=[0.1, 0.25, 1.0],
                    help="fractions of the other pages that are labelled evidence")
    ap.add_argument("--tau", type=float, default=0.85)
    ap.add_argument("--unsure-below", type=float, default=0.0)
    args = ap.parse_args()
    make = (lambda: Boost(rounds=300, depth=2)) if args.model == "boost" else (lambda: LogReg())
    rows, lex = load()
    folds = page_folds(rows)
    y = [r["label"] for r in rows]
    stmts = statements_out_of_fold(rows, lex, folds, args.oracle)
    report([(g, "true") for g in y], "always true")
    all_X1, all_X2, all_y = [], [], []
    for frac in args.labelled:
        X1, X2, P1, P2 = simulate(rows, lex, folds, stmts, frac, make, args.tau)
        for name, P in (("pass 1", P1), ("pass 2, self-trained", P2)):
            preds = [decide(p, args.unsure_below) for p in P]
            report([(t, lab) for t, (lab, _) in zip(y, preds)],
                   f"{name}, {int(frac * 100)}% of the other pages labelled")
        calibration(y, [decide(p, args.unsure_below) for p in P2])
        all_X1 += X1
        all_X2 += X2
        all_y += y
    if not args.no_save:
        meta = {"rows": len(rows), "oracle": args.oracle, "labelled": args.labelled, "tau": args.tau,
                "trained_on": "simulated runs over data/practice.csv, 5 page-grouped folds"}
        make().fit(all_X1, all_y).save(meta=dict(meta, passes="1"))
        make().fit(all_X2, all_y).save(PASS2_PATH, meta=dict(meta, passes="2"))
        print("saved arena/ml/model.json and arena/ml/model_pass2.json")


if __name__ == "__main__":
    sys.exit(main())
