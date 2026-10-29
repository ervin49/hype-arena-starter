"""Write data/claims_fallback.csv: the claims a run uses if its claim generation fails.

Built once from the practice data alone, as the run would build them (the practice sentences,
which the real input holds, as the input texts the claims must not repeat). The image copies
data/, so the file is there at run time (arena.runner.read_claims_fallback). Check it with the
independent referee before committing it:

    .venv/bin/python scripts/claims_fallback.py
    .venv/bin/python scripts/referee.py --input data/practice.csv data/claims_fallback.csv
"""
import csv
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.generate import select_claims  # noqa: E402
from arena.io import OUTPUT_COLUMNS, output_rows, read_lexicon, read_rows  # noqa: E402
from arena.runner import AS_OF, CLAIMS, CLAIMS_FALLBACK  # noqa: E402


def main():
    practice = read_rows(os.path.join(ROOT, "data", "practice.csv"), require_form=True)
    lexicon = read_lexicon(os.path.join(ROOT, "data", "lexicon.json"))
    claims, _ = select_claims(practice, lexicon, AS_OF, [r["text"] for r in practice], CLAIMS)
    with open(CLAIMS_FALLBACK, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        w.writeheader()
        w.writerows(output_rows([], claims))
    print(f"wrote {os.path.relpath(CLAIMS_FALLBACK, ROOT)}: {len(claims)} claims")


if __name__ == "__main__":
    main()
