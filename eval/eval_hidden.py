"""The hidden practice rows, as scripts/check.sh hides them.

The input is the practice data with every fifth label hidden; the engine
learns from the rows whose label the input shows (arena.runner's
known_practice) and labels the hidden ones. Measured two ways:

- runner path: classify row by row, as arena.runner does today (pass 1);
- label_rows: page context, corroboration and self-training (pass 2).

By default the engine uses the shipped models, which were trained on every
practice row, the hidden ones too: an upper bound, as check.sh's count is.
With --honest both models are first retrained on the visible rows only, so
nothing about a hidden row is learned before it is labelled.

    python3 eval/eval_hidden.py [--honest]
"""

import argparse
import sys
from collections import defaultdict

from common import load
from train_model import ece, reliability, train

from arena.classify import classify, label_rows
from arena.extract import build_extractor, extract
from arena.truth import build_kb, check_fact


def known_practice(practice, universe_rows):
    """Practice rows whose label the input shows (as arena.runner reads them)."""
    labelled = {r["id"]: r["label"] for r in universe_rows if r["label"]}
    return [r for r in practice if labelled.get(r["id"]) == r["label"]]


def show(name, preds, gold):
    y = [gold[p["id"]] for p in preds]
    pairs = [(p["label"], p["confidence"]) for p in preds]
    right = sum(t == lab for t, (lab, _) in zip(y, pairs))
    false_rows = sum(t == "false" for t in y)
    caught = sum(t == lab == "false" for t, (lab, _) in zip(y, pairs))
    called = sum(lab == "false" for lab, _ in pairs)
    print(f"{name}: {right}/{len(preds)} right ({right / len(preds):.3f}); "
          f"false caught {caught}/{false_rows}, false precision {caught}/{called}; "
          f"ECE {ece(y, pairs):.3f}")
    for b in reliability(y, pairs):
        print(f"    {b['label']:>5} {b['from']:.1f}-{b['to']:.1f}: {b['n']:>4} rows, "
              f"right {b['accuracy']:.2f}, said {b['confidence']:.2f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--honest", action="store_true", help="retrain the models on the visible rows first")
    args = ap.parse_args()
    rows, lex = load()
    gold = {r["id"]: r["label"] for r in rows}
    universe = [dict(id=r["id"], text=r["text"], date=r["date"], label="" if i % 5 == 0 else r["label"])
                for i, r in enumerate(rows)]
    visible = known_practice(rows, universe)
    print(f"{len(universe)} rows, {sum(not r['label'] for r in universe)} hidden; "
          f"{'models retrained on the visible rows' if args.honest else 'shipped models (upper bound)'}")
    models = train(visible, lex) if args.honest else None
    m1 = models[0] if models else "default"

    kb = build_kb(visible, lex)
    ex = build_extractor(visible, lex)
    check = lambda fact, date: check_fact(fact, date, kb)
    per_row = []
    for r in universe:
        if not r["label"]:
            per_row.append(classify(r, extract(r, lex, ex), check, model=m1))
    show("runner path (row by row, pass 1)", per_row, gold)
    show("label_rows (context, corroboration, self-training)",
         label_rows(universe, visible, lex, models=models), gold)


if __name__ == "__main__":
    sys.exit(main())
