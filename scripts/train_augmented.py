"""Train the label models on real + synthetic lies (eval/augment.py); test and calibrate on real rows only.

The run of eval/train_model.py, with one change: each fold's models also learn from synthetic
false rows. A synthetic row sits in its source row's fold and page: it is read by the extractor
of that fold, checked against that fold's base with the source's page left out, and trained on
only by the models that never see that fold. The extractors, the bases and the self-training
see real rows only, so a real row's features are exactly what train_model computes; only the
model changes. Every prediction scored, and every Platt calibration, is on real rows out of
fold: the synthetic share would otherwise skew every confidence.

    .venv/bin/python scripts/train_augmented.py --ratio 0 0.5 1 2            # out of fold, ~2 min each
    .venv/bin/python scripts/train_augmented.py --ratio 0 1 --shift          # scripts/shift_test.py, ~8 min each

--ratio: synthetic rows per real false row (0 is the current engine). Saves no model: A
retrains the shipped ones with train_augmented(rows, lex, ratio).
"""
import argparse
import json
import math
import os
import sys
from collections import Counter
from multiprocessing import Pool

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from augment import augment  # noqa: E402
from common import load, page_folds  # noqa: E402
from train_model import (CALIBRATE_ON, cross_fitted, ece, low_bins, make_model, reliability,  # noqa: E402
                         setups)

from arena.extract import build_extractor, extract_batch  # noqa: E402
from arena.ml.model import Calibration, featurize  # noqa: E402
from arena.truth import check_fact, page_groups  # noqa: E402

LABELLED = (0.1, 0.25, 1.0)
TAU = 0.85


def statements(rows, synth, lex, folds, fold_of):
    """What every real and synthetic row states, read by the extractor of its fold (real rows only)."""
    st, sst = [None] * len(rows), [None] * len(synth)
    for k, test in enumerate(folds):
        held = set(test)
        ex = build_extractor([r for i, r in enumerate(rows) if i not in held], lex)
        mine = [j for j in range(len(synth)) if fold_of[j] == k]
        exs = extract_batch([dict(rows[i], label="") for i in sorted(test)] + [dict(synth[j], label="") for j in mine],
                            lex, ex)
        for i, e in zip(sorted(test), exs):
            st[i] = e
        for j, e in zip(mine, exs[len(test):]):
            sst[j] = e
    return st, sst


def _feats(row, stmt, kb, own):
    r = dict(row, label="")
    return featurize(r, stmt, [check_fact(f, r["date"], kb, own) for f in stmt["facts"]])


def features(rows, synth, st, sst, kbs, own_page, fold_of):
    """Real and synthetic features per fold's base; a synthetic row leaves its source's page out."""
    X, SX = [None] * len(rows), [None] * len(synth)
    for k, (test, kb) in enumerate(kbs):
        for i in test:
            X[i] = _feats(rows[i], st[i], kb, own_page[rows[i]["id"]])
        for j in range(len(synth)):
            if fold_of[j] == k:
                SX[j] = _feats(synth[j], sst[j], kb, own_page[synth[j]["source"]])
    return X, SX


def out_of_fold(Xs, SXs, y, folds, fold_of, make):
    """Each fold's real rows predicted by a model trained on the other folds' real and synthetic rows."""
    Ps = {frac: [None] * len(y) for frac in Xs}
    for k, test in enumerate(folds):
        held = set(test)
        trX, trY = [], []
        for frac in Xs:
            for i in range(len(y)):
                if i not in held:
                    trX.append(Xs[frac][i])
                    trY.append(y[i])
            for j, x in enumerate(SXs[frac]):
                if fold_of[j] != k:
                    trX.append(x)
                    trY.append("false")
        m = make().fit(trX, trY)
        for frac, X in Xs.items():
            for i in test:
                Ps[frac][i] = m.probs(X[i])
    return Ps


def simulate(rows, synth, lex, make, labelled=LABELLED, tau=TAU):
    """train_model.simulate with the synthetic rows in training only."""
    folds = page_folds(rows)
    fold_idx = {i: k for k, t in enumerate(folds) for i in t}
    row_idx = {r["id"]: i for i, r in enumerate(rows)}
    fold_of = [fold_idx[row_idx[s["source"]]] for s in synth]
    y = [r["label"] for r in rows]
    own_page = page_groups(rows)
    unl = [dict(r, label="") for r in rows]
    st, sst = statements(rows, synth, lex, folds, fold_of)
    sets = {frac: setups(rows, lex, folds, st, frac) for frac in labelled}
    X1, SX1 = {}, {}
    for frac, s in sets.items():
        X1[frac], SX1[frac] = features(rows, synth, st, sst, [(t, kb) for t, kb, _ in s], own_page, fold_of)
    P1 = out_of_fold(X1, SX1, y, folds, fold_of, make)
    X2, SX2 = {}, {}
    for frac, s in sets.items():
        kb2s = [(test, kb.with_pseudo([unl[i] for i in pool], [st[i] for i in pool], [P1[frac][i] for i in pool], tau))
                for test, kb, pool in s]
        X2[frac], SX2[frac] = features(rows, synth, st, sst, kb2s, own_page, fold_of)
    P2 = out_of_fold(X2, SX2, y, folds, fold_of, make)
    return folds, (X1, SX1, P1), (X2, SX2, P2)


def n_synthetic(rows, ratio):
    return round(ratio * sum(r["label"] == "false" for r in rows))


def train_augmented(rows, lex, ratio=1.0, seed=0, kind="boost", mix=None):
    """Pass-1 and pass-2 models on real + synthetic rows, each calibrated on real out-of-fold predictions.

    Same use as eval/train_model.train(rows, lex); the synthetic lies are made from these rows only."""
    make = make_model(kind)
    synth = augment(rows, lex, n_synthetic(rows, ratio), seed=seed, mix=mix) if ratio else []
    y = [r["label"] for r in rows]
    _, *passes = simulate(rows, synth, lex, make)
    out = []
    for X, SX, P in passes:
        m = make().fit([x for frac in X for x in X[frac]] + [x for frac in SX for x in SX[frac]],
                       y * len(X) + ["false"] * sum(len(v) for v in SX.values()))
        m.calibration = Calibration.fit([p["true"] for p in P[CALIBRATE_ON]], y)
        out.append(m)
    return out


def score(y, preds):
    """Accuracy, lies caught, false precision, ECE, log loss and over-confident bins of calibrated preds."""
    caught = sum(t == lab == "false" for t, (lab, _) in zip(y, preds))
    called = sum(lab == "false" for lab, _ in preds)
    ll = -sum(math.log(max(c if t == lab else 1 - c, 1e-6)) for t, (lab, c) in zip(y, preds) if c is not None) / len(y)
    return {"accuracy": round(sum(t == lab for t, (lab, _) in zip(y, preds)) / len(y), 4),
            "lies_caught": caught, "lies": sum(t == "false" for t in y), "false_called": called,
            "ece": round(ece(y, preds), 4), "logloss": round(ll, 4), "low_bins": len(low_bins(y, preds))}


def run_oof(ratio, seed=0, mix=None):
    rows, lex = load()
    synth = augment(rows, lex, n_synthetic(rows, ratio), seed=seed, mix=mix) if ratio else []
    folds, *passes = simulate(rows, synth, lex, make_model())
    y = [r["label"] for r in rows]
    res = {"ratio": ratio, "seed": seed, "synthetic": len(synth), "mix": dict(Counter(s["lie"] for s in synth))}
    for name, (_, _, P) in zip(("pass1", "pass2"), passes):
        for frac in LABELLED:
            cal = cross_fitted(y, P[frac], folds, 0.0)
            res[f"{name}@{frac}"] = score(y, cal)
            if name == "pass2" and frac == CALIBRATE_ON:
                res["bins"] = reliability(y, cal)
    return res


def run_shift(ratio, seed=0, mix=None):
    import shift_test
    shift_test.train = lambda rows, lex: train_augmented(rows, lex, ratio, seed, mix=mix)
    rows, lex = load()
    out = []
    for name, split in (("random pages", shift_test.split_random), ("latest pages", shift_test.split_time),
                        ("held-out subjects", shift_test.split_subjects)):
        r = shift_test.scenario(name, rows, lex, split(rows))
        out.append({"scenario": name, "always_true": r["always_true"], "before": r["unseen_before"],
                    "after": r["unseen_after"], "factors": r["factors"]})
    return {"ratio": ratio, "shift": out}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ratio", type=float, nargs="+", default=[0, 0.5, 1, 2])
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--mix", help="lie mix instead of the real one, e.g. wrong=0,stale=103,early=67")
    ap.add_argument("--shift", action="store_true", help="run scripts/shift_test.py's scenarios instead")
    ap.add_argument("--out", help="write the results to this JSON file")
    args = ap.parse_args()
    sys.path.insert(0, os.path.join(ROOT, "scripts"))
    job = run_shift if args.shift else run_oof
    mix = {k: float(v) for k, v in (p.split("=") for p in args.mix.split(","))} if args.mix else None
    with Pool(min(len(args.ratio), os.cpu_count() or 1)) as pool:
        results = pool.starmap(job, [(r, args.seed, mix) for r in args.ratio])
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=1)
            f.write("\n")
    if args.shift:
        print(f"{'ratio':>5} {'scenario':18} {'right':>6} {'always':>6} {'said':>6} {'ECE':>6} {'Brier':>7}")
        for r in results:
            for s in r["shift"]:
                b = s["after"]
                print(f"{r['ratio']:5} {s['scenario']:18} {b['right']:6.3f} {s['always_true']:6.3f} {b['said']:6.3f} "
                      f"{b['ece']:6.3f} {b['brier']:7.4f}")
        return
    print(f"{'ratio':>5} {'synth':>5} {'regime':10} {'acc':>6} {'lies':>8} {'called':>6} {'ECE':>6} {'logloss':>7} {'low':>3}")
    for r in results:
        for key in [k for k in r if "@" in k]:
            s = r[key]
            print(f"{r['ratio']:5} {r['synthetic']:5} {key:10} {s['accuracy']:6.3f} {s['lies_caught']:4}/{s['lies']:<3} "
                  f"{s['false_called']:6} {s['ece']:6.3f} {s['logloss']:7.4f} {s['low_bins']:3}")


if __name__ == "__main__":
    main()
