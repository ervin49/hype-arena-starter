"""Extraction against the practice forms, with page-grouped cross-validation.

    python3 eval/eval_extract.py [--errors N]
"""

import argparse
import sys
from collections import Counter

from common import facts, load, page_folds

from arena.extract import build_extractor, extract_batch
from arena.values import values_equal


def same_fact(a, b):
    return (a["subject"] == b["subject"] and a["attribute"] == b["attribute"]
            and values_equal({k: v for k, v in a["value"].items() if k != "op"},
                             {k: v for k, v in b["value"].items() if k != "op"})
            and a["value"].get("op") == b["value"].get("op"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--errors", type=int, default=0)
    ap.add_argument("--k", type=int, default=5)
    ap.add_argument("--none-bias", type=float, default=None)
    ap.add_argument("--bool-bias", type=float, default=None)
    ap.add_argument("--prior", type=float, default=None, help="naive Bayes prior strength")
    args = ap.parse_args()
    rows, lex = load()
    tp = fp = fn = exact_rows = 0
    parts = Counter()
    errors = []
    for test in page_folds(rows, args.k):
        held = set(test)
        train = [r for i, r in enumerate(rows) if i not in held]
        ex = build_extractor(train, lex)
        if args.none_bias is not None:
            ex.none_bias = args.none_bias
        if args.bool_bias is not None:
            ex.bool_bias = args.bool_bias
        if args.prior is not None:
            for nb in (ex.nb, ex.nb_row, ex.nb_bool):
                nb.prior = args.prior
        test_rows = [dict(rows[i], label="") for i in sorted(test)]
        outs = extract_batch(test_rows, lex, ex)
        for r, out in zip(test_rows, outs):
            gold, got = facts(r), out["facts"]
            matched = [g for g in gold if any(same_fact(g, x) for x in got)]
            tp += len(matched)
            fn += len(gold) - len(matched)
            fp += sum(1 for x in got if not any(same_fact(g, x) for g in gold))
            exact_rows += len(matched) == len(gold) == len(got)
            for g in gold:
                parts["subject"] += any(x["subject"] == g["subject"] for x in got)
                parts["subject+attribute"] += any(
                    x["subject"] == g["subject"] and x["attribute"] == g["attribute"] for x in got)
                parts["gold facts"] += 1
            if len(matched) != len(gold) or len(got) != len(gold):
                errors.append((r, gold, out))
    p, rc = tp / max(1, tp + fp), tp / max(1, tp + fn)
    print(f"facts: precision {p:.3f}, recall {rc:.3f}, F1 {2 * p * rc / max(1e-9, p + rc):.3f}")
    print(f"rows extracted exactly: {exact_rows} of {len(rows)} ({exact_rows / len(rows):.3f})")
    for k in ("subject", "subject+attribute"):
        print(f"gold facts with the right {k}: {parts[k] / parts['gold facts']:.3f}")
    for r, gold, out in errors[:args.errors]:
        print("\n", r["id"], r["date"], r["text"])
        print("  gold:", [(g["subject"], g["attribute"], g["value"]) for g in gold])
        print("  got: ", [(g["subject"], g["attribute"], g["value"]) for g in out["facts"]], out["issues"])


if __name__ == "__main__":
    sys.exit(main())
