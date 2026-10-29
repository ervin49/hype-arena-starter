"""Train the control model: A's models (eval/train_model.py), on the practice pages outside a
fixed control group, so that the control group's labels are never learned from.

At run time arena/controls.py labels the control group with this model, in the context of the
real input, and lowers the confidence of every answer as far as the control group shows it is
over-stated. Writes arena/control/{model,model_pass2,ids}.json, then reports/controls.json: what
the control shows on the practice data (served by GET /metrics). Takes about 1.5 minutes.

    .venv/bin/python scripts/train_control.py                # train, then report
    .venv/bin/python scripts/train_control.py --report-only  # the report, with the saved model
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "eval"))

from common import load, page_folds  # noqa: E402
from train_model import train  # noqa: E402

from arena import controls  # noqa: E402
from arena.classify import label_rows  # noqa: E402
from arena.controls import CONTROL_DIR, CONTROL_FOLD, CONTROL_FOLDS, CONTROL_SEED  # noqa: E402

REPORT = os.path.join(ROOT, "reports", "controls.json")


def report(rows, lex):
    """The confidence control as the run applies it, on the practice data as input."""
    ids, m1, m2 = controls.load_control()
    hidden, practice_out, group, _ = controls.control_input(rows, rows, ids)
    members = set(group)
    answers = label_rows(hidden, practice_out, lex, models=(m1, m2))
    factors, rep = controls.measure([p for p in answers if p["id"] in members],
                                    {r["id"]: r["label"] for r in rows if r["id"] in members})
    out = {"input": "data/practice.csv, the control group's labels hidden", "control_rows": len(members), **rep}
    with open(REPORT, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
        f.write("\n")
    print(f"control on practice: {out}")


def main():
    rows, lex = load()
    if "--report-only" in sys.argv:
        return report(rows, lex)
    held = set(page_folds(rows, CONTROL_FOLDS, seed=CONTROL_SEED)[CONTROL_FOLD])
    control_ids = [r["id"] for i, r in enumerate(rows) if i in held]
    rest = [r for i, r in enumerate(rows) if i not in held]
    m1, m2 = train(rest, lex)
    os.makedirs(CONTROL_DIR, exist_ok=True)
    meta = {"trained_on": f"data/practice.csv without the control group: {len(rest)} rows",
            "control_rows": len(control_ids), "folds": CONTROL_FOLDS, "fold": CONTROL_FOLD, "seed": CONTROL_SEED}
    m1.save(os.path.join(CONTROL_DIR, "model.json"), meta=dict(meta, passes="1"))
    m2.save(os.path.join(CONTROL_DIR, "model_pass2.json"), meta=dict(meta, passes="2"))
    with open(os.path.join(CONTROL_DIR, "ids.json"), "w", encoding="utf-8") as f:
        json.dump({"meta": meta, "ids": control_ids}, f, indent=0)
        f.write("\n")
    print(f"control group: {len(control_ids)} rows; model trained on {len(rest)}; wrote {os.path.relpath(CONTROL_DIR, ROOT)}/")
    report(rows, lex)


if __name__ == "__main__":
    main()
