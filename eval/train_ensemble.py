"""Train the ensemble: 5 pass-1 + pass-2 model pairs, each without one page fold.

Model k is trained (and calibrated) by train_model.train() on every practice
row except the pages of fold k (common.page_folds(rows, 5, seed=0)), so the
five see different data and their disagreement ("spread") says how much a
prediction depends on which rows the model learned from. The folds train in
parallel, one process each.

Saves arena/ml/ensemble/model_{k}.json and model_pass2_{k}.json.

    python3 eval/train_ensemble.py
"""

import os
import sys
from multiprocessing import Pool

from common import ROOT, load, page_folds
from train_model import train

ENSEMBLE_DIR = os.path.join(ROOT, "arena", "ml", "ensemble")
K = 5


def fit(k):
    rows, lex = load()
    held = set(page_folds(rows, K, seed=0)[k])
    rest = [r for i, r in enumerate(rows) if i not in held]
    m1, m2 = train(rest, lex)
    meta = {"rows": len(rest), "fold_left_out": k, "folds": K,
            "trained_on": "eval/train_model.train() on data/practice.csv without one page fold"}
    m1.save(os.path.join(ENSEMBLE_DIR, f"model_{k}.json"), meta=dict(meta, passes="1"))
    m2.save(os.path.join(ENSEMBLE_DIR, f"model_pass2_{k}.json"), meta=dict(meta, passes="2"))
    return k, len(rest)


def main():
    os.makedirs(ENSEMBLE_DIR, exist_ok=True)
    with Pool(K) as pool:
        for k, n in pool.imap_unordered(fit, range(K)):
            print(f"model pair {k}: trained on {n} rows", flush=True)
    print(f"saved {K} pairs in {os.path.relpath(ENSEMBLE_DIR, ROOT)}")


if __name__ == "__main__":
    sys.exit(main())
