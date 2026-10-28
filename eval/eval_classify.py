"""End-to-end labels with page-grouped cross-validation.

Each fold builds the base and the extractor from the other folds only, then
labels the fold's rows from their text and date, as the run does.

    python3 eval/eval_classify.py [--oracle] [--errors N]

--oracle uses the gold forms instead of the extractor: the ceiling of the
checker alone.
"""

import argparse
import sys
from collections import Counter

from common import facts, load, page_folds

from arena.classify import classify
from arena.extract import build_extractor, extract_batch
from arena.truth import build_kb, check_fact

LABELS = ("true", "false", "unsure")


def report(pairs, title):
    conf = Counter(pairs)
    n = len(pairs)
    print(f"== {title}: {n} rows, accuracy {sum(conf[(g, g)] for g in LABELS) / n:.3f}")
    print("gold \\ pred " + " ".join(f"{p:>7}" for p in LABELS))
    for g in LABELS:
        print(f"{g:>11} " + " ".join(f"{conf[(g, p)]:>7}" for p in LABELS))
    for c in LABELS:
        tp = conf[(c, c)]
        pp = sum(conf[(g, c)] for g in LABELS)
        gp = sum(conf[(c, p)] for p in LABELS)
        p, r = tp / max(1, pp), tp / max(1, gp)
        print(f"{c:>7}: precision {p:.3f} recall {r:.3f} F1 {2 * p * r / max(1e-9, p + r):.3f}")
    firm = [(g, p) for g, p in pairs if p != "unsure"]
    if firm:
        print(f"firm labels: {len(firm)} ({len(firm) / n:.3f}), right {sum(g == p for g, p in firm) / len(firm):.3f}")


def run(rows, lex, k=5, oracle=False):
    """[(row, prediction)] for every row, each labelled by a model that never saw its page."""
    out = []
    for test in page_folds(rows, k):
        held = set(test)
        train = [r for i, r in enumerate(rows) if i not in held]
        kb = build_kb(train, lex)
        test_rows = [dict(rows[i], label="") for i in sorted(test)]
        if oracle:
            exs = [{"facts": facts(r), "complete": True, "issues": [], "scores": []} for r in test_rows]
        else:
            exs = extract_batch(test_rows, lex, build_extractor(train, lex))
        check = lambda fact, date: check_fact(fact, date, kb)
        for r, ex in zip(test_rows, exs):
            out.append((r, classify(r, ex, check, model=None), ex))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", action="store_true")
    ap.add_argument("--errors", type=int, default=0)
    args = ap.parse_args()
    rows, lex = load()
    gold = {r["id"]: r["label"] for r in rows}
    res = run(rows, lex, oracle=args.oracle)
    report([(gold[r["id"]], p["label"]) for r, p, _ in res], "oracle forms" if args.oracle else "extracted")
    kinds = Counter((p.get("kind"), gold[r["id"]]) for r, p, _ in res)
    print("by reason:", dict(sorted(kinds.items())))
    shown = 0
    for r, p, ex in res:
        if shown >= args.errors:
            break
        if p["label"] != gold[r["id"]]:
            shown += 1
            print(f"\n{r['id']} {r['date']} gold={gold[r['id']]} pred={p['label']} {r['text']}")
            print("   ", p["reason"])


if __name__ == "__main__":
    sys.exit(main())
