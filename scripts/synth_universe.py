"""Density test v2 (PLAN_ENGINE.md section 5): a ~16,000-row input as dense as the real one.

The run's real input is about 10x denser than practice: most facts are stated by several
independent sources. Our first synthetic 20k repeated sentences verbatim, so source_key folded
them into one source and the dense regime was never tested. This one:

- keeps every practice row, every fifth label hidden (as scripts/input.py does);
- gives each row labelled true 9 copies, and each row labelled false 1 (unsure rows none): new
  ids, the same date, an empty label, and a text varied so that its source_key differs: a prefix
  ("Note:", "Update:", "As announced,", "For the record,"), a suffix sentence ("That is the
  figure.", "We checked it.") or another number format (2,600 / 2600). A variant is kept only if
  arena.values reads exactly the same values from it: never a changed value;
- puts each row's copies right after it, in the practice order: a page (consecutive rows with
  one date) stays contiguous and whole, no two pages merge, and a hidden row's own copies, on its
  page, never count for it. (Sorting by date would merge practice's 291 pages into 159: practice
  is not in date order.) With no copies the input is exactly scripts/input.py's.

    .venv/bin/python scripts/synth_universe.py build OUT_DIR          # OUT_DIR/universe.csv + lexicon.json
    .venv/bin/python scripts/synth_universe.py run [--keep DIR]       # build, run the runner, report
    .venv/bin/python scripts/synth_universe.py run --copies 0 0       # the same on the plain input (before)

`run` reports: hidden-row accuracy and lies caught, the control factors k, the false share on the
input against the control group, run time and peak memory, and scripts/check_output.py's verdict.
"""
import argparse
import csv
import json
import os
import random
import re
import resource
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from arena.truth import source_key  # noqa: E402
from arena.values import parse_values  # noqa: E402

PRACTICE = os.path.join(ROOT, "data", "practice.csv")
LEXICON = os.path.join(ROOT, "data", "lexicon.json")
EVERY = 5
COPIES = {"true": 9, "false": 1}
PREFIXES = ["", "Note: ", "Update: ", "As announced, ", "For the record, "]
SUFFIXES = ["", " That is the figure.", " We checked it."]
# a lower-case start after "As announced," / "For the record," only for these plain words
LOWER_AFTER_COMMA = {"The", "It", "Its", "It's", "Our", "We", "This", "These", "A", "An", "Every", "Each", "All"}


def _values(text):
    return [(v["value"], v.get("approx"), v.get("range"), v.get("negated")) for v in parse_values(text)]


def number_variants(text):
    """The text with its thousands commas dropped (2,600 -> 2600), when that stays the same number:
    never a plain four-digit 1900-2099, which reads as a year."""
    def drop(m):
        plain = m.group(0).replace(",", "")
        if re.fullmatch(r"(19|20)\d\d", plain.split(".")[0]):
            return m.group(0)
        return plain
    alt = re.sub(r"(?<![\w.,])\d{1,3}(?:,\d{3})+(?:\.\d+)?(?![\w,]|\.\d)", drop, text)
    return [alt] if alt != text else []


def variants(text):
    """Every varied text: prefixes, suffixes and the number format, each with another source_key."""
    bodies = [text] + number_variants(text)
    out = []
    for body in bodies:
        for p in PREFIXES:
            b = body
            if p.endswith(", "):
                first = b.split(" ", 1)[0]
                if first in LOWER_AFTER_COMMA:
                    b = b[0].lower() + b[1:]
            for s in SUFFIXES:
                # a suffix sentence after a sentence end; a headline is closed with a full stop first
                end = b if not s or re.search(r"[.!?]$", b.rstrip()) else b.rstrip() + "."
                t = p + end + s
                if t != text:
                    out.append(t)
    return out


def build(practice=PRACTICE, every=EVERY, seed=0, copies=None):
    """(rows for universe.csv, stats). copies: {label: copies per row}; {} is scripts/input.py's input."""
    copies = COPIES if copies is None else copies
    with open(practice, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    rng = random.Random(seed)
    out, short, rejected = [], 0, 0
    for i, r in enumerate(rows):
        label = "" if i % every == 0 else r["label"]
        out.append({"id": r["id"], "text": r["text"], "date": r["date"], "label": label})
        n = copies.get(r["label"], 0)
        if not n:
            continue
        want = _values(r["text"])
        keys = {source_key(r["text"])}
        pool = variants(r["text"])
        rng.shuffle(pool)
        made = 0
        for t in pool:
            if made >= n:
                break
            k = source_key(t)
            if k in keys:
                continue
            if _values(t) != want:
                rejected += 1
                continue
            keys.add(k)
            made += 1
            out.append({"id": f"{r['id']}.c{made}", "text": t, "date": r["date"], "label": ""})
        short += n - made
    return out, {"practice": len(rows), "hidden": sum(1 for i in range(len(rows)) if i % every == 0),
                 "rows": len(out), "copies": len(out) - len(rows), "copies_short": short,
                 "variants_rejected_for_values": rejected}


def write(rows, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    with open(os.path.join(out_dir, "universe.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "text", "date", "label"])
        w.writeheader()
        w.writerows(rows)
    shutil.copy(LEXICON, os.path.join(out_dir, "lexicon.json"))


def run(keep=None, minutes=30, copies=None):
    work = keep or tempfile.mkdtemp(prefix="synth-universe-")
    uni, outd = os.path.join(work, "universe"), os.path.join(work, "output")
    rows, stats = build(copies=copies)
    write(rows, uni)
    os.makedirs(outd, exist_ok=True)
    env = dict(os.environ, ARENA_UNIVERSE=uni, ARENA_OUTPUT=outd, ARENA_DEADLINE=str(int(time.time()) + minutes * 60))
    t0 = time.time()
    proc = subprocess.run([sys.executable, "-W", "ignore", "-m", "arena.runner"], cwd=ROOT, env=env,
                          capture_output=True, text=True)
    seconds = time.time() - t0
    peak_mib = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024
    log = proc.stdout + proc.stderr
    with open(os.path.join(work, "runner.log"), "w", encoding="utf-8") as f:
        f.write(log)

    gold = {}
    with open(PRACTICE, encoding="utf-8-sig", newline="") as f:
        for i, r in enumerate(csv.DictReader(f)):
            if i % EVERY == 0:
                gold[r["id"]] = r["label"]
    got = {}
    with open(os.path.join(outd, "output.csv"), encoding="utf-8", newline="") as f:
        for r in csv.DictReader(f):
            if not r["type"] and r["id"] in gold and r["id"] not in got:
                got[r["id"]] = r["label"]
    right = sum(got.get(i) == lab for i, lab in gold.items())
    lies = sum(lab == "false" for lab in gold.values())
    caught = sum(lab == "false" and got.get(i) == "false" for i, lab in gold.items())
    called = sum(got.get(i) == "false" for i in gold)

    control = re.search(r"confidence control: (\d+) held-out rows; (\{.*\})", log)
    monitor = re.search(r"distribution monitor: (.*)", log)
    report = {}
    if control:
        try:
            report = eval(control.group(2), {"__builtins__": {}})  # the runner logs a Python dict
        except Exception:
            report = {"raw": control.group(2)}
    check = subprocess.run([sys.executable, os.path.join(ROOT, "scripts", "check_output.py"), outd, PRACTICE,
                            os.path.join(uni, "universe.csv")], capture_output=True, text=True)
    result = {
        "input": stats,
        "runner_exit": proc.returncode,
        "seconds": round(seconds, 1),
        "peak_mib": round(peak_mib),
        "hidden": len(gold), "hidden_right": right, "hidden_accuracy": round(right / len(gold), 3),
        "lies": lies, "lies_caught": caught, "false_called": called,
        "control_rows": int(control.group(1)) if control else None,
        "control_factors": report.get("factors"),
        "control_false_share": report.get("false_share"),
        "monitor": monitor.group(1).strip() if monitor else None,
        "check_output": (check.stdout + check.stderr).strip().splitlines()[-3:],
        "check_exit": check.returncode,
        "work": work,
    }
    return result


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("out_dir")
    r = sub.add_parser("run")
    r.add_argument("--keep", help="work directory to keep (default: a temporary one)")
    r.add_argument("--minutes", type=int, default=30)
    for p in (b, r):
        p.add_argument("--copies", type=int, nargs=2, metavar=("TRUE", "FALSE"),
                       help="copies per true and per false row (default 9 1; 0 0 is the plain input)")
    args = ap.parse_args()
    copies = {"true": args.copies[0], "false": args.copies[1]} if args.copies else None
    if args.cmd == "build":
        rows, stats = build(copies=copies)
        write(rows, args.out_dir)
        print(json.dumps(stats))
        return 0
    res = run(args.keep, args.minutes, copies)
    print(json.dumps(res, indent=1))
    return 0 if res["runner_exit"] == 0 and res["check_exit"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
