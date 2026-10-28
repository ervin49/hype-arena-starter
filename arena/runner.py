"""Batch runner: /universe in, /output/output.csv out.

Order of work, so that a complete table is on disk as early as possible:
1. read the input, generate and validate the claims;
2. write a first complete table: the claims, and every unlabelled row unsure;
3. classify the unlabelled rows with the engine, rewriting the table now and then;
4. write the final table. Every write is atomic (arena.io.write_output).
"""
import os
import signal
import sys
import time
import traceback
from types import SimpleNamespace

from arena.io import read_lexicon, read_rows, split_rows, write_output

AS_OF = "2026-10-29"
CLAIMS = 1000
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REWRITE_EVERY_S = 60
DEADLINE_MARGIN_S = 25


def log(*args):
    print(time.strftime("%H:%M:%S"), *args, file=sys.stderr, flush=True)


def import_engine():
    """A's public functions (contract v1, plus label_rows for the batch). No fallback:
    a failed import is raised."""
    from arena.classify import classify, label_rows
    from arena.extract import build_extractor, extract
    from arena.truth import build_kb, check_fact
    return SimpleNamespace(build_kb=build_kb, check_fact=check_fact, build_extractor=build_extractor,
                           extract=extract, classify=classify, label_rows=label_rows)


class Pipeline:
    """The engine, built once, as the runner and the API call it."""

    def __init__(self, practice_rows, lexicon, engine=None):
        self.engine = engine or import_engine()
        self.lexicon = lexicon
        self.practice = practice_rows
        self.kb = self.engine.build_kb(practice_rows, lexicon)
        self.extractor = self.engine.build_extractor(practice_rows, lexicon)

    def predict(self, row):
        """The v1 prediction, with the extraction attached for display."""
        e = self.engine
        extraction = e.extract(row, self.lexicon, self.extractor)
        check = lambda fact, date: e.check_fact(fact, date, self.kb)
        prediction = dict(e.classify(row, extraction, check))
        prediction["id"] = row["id"]
        prediction["extraction"] = extraction
        return prediction

    def label_all(self, rows):
        """The whole input at once, in file order, as A's label_rows reads it: page context
        and corroboration across rows. None when the engine has no batch function."""
        batch = getattr(self.engine, "label_rows", None)
        if batch is None:
            return None
        return batch(rows, self.practice, self.lexicon, kb=self.kb, extractor=self.extractor)


def known_practice(practice, universe_rows):
    """Practice rows (with forms) whose label the input shows.

    In the real run every practice row is labelled in the input. In scripts/check.sh
    every fifth label is hidden, and this keeps their forms out of what we learn from.
    """
    labelled = {r["id"]: r["label"] for r in universe_rows if r["label"]}
    return [r for r in practice if labelled.get(r["id"]) == r["label"]]


def deadline_from_env():
    try:
        return float(os.environ["ARENA_DEADLINE"]) - DEADLINE_MARGIN_S
    except (KeyError, ValueError):
        return None


class Stop(Exception):
    pass


def _on_sigterm(signum, frame):
    raise Stop()


def run(universe_dir, output_dir, practice_path, engine=None, deadline=None, claims_target=CLAIMS):
    from arena.generate import select_claims

    out = os.path.join(output_dir, "output.csv")
    rows = read_rows(os.path.join(universe_dir, "universe.csv"))
    lexicon = read_lexicon(os.path.join(universe_dir, "lexicon.json"))
    labelled, unlabelled = split_rows(rows)
    all_practice = read_rows(practice_path, require_form=True)
    practice = known_practice(all_practice, rows)
    log(f"input: {len(rows)} rows, {len(unlabelled)} unlabelled; practice with forms: "
        f"{len(all_practice)}, of which the engine sees {len(practice)}")

    # Claims come from the whole practice file, as in the real run where every practice
    # row is labelled; the engine sees only the labels the input shows (no leakage into labels).
    claims, report = select_claims(all_practice, lexicon, AS_OF, [r["text"] for r in rows], claims_target)
    log(f"claims: {len(claims)} selected; {report}")
    predictions = {r["id"]: {"id": r["id"], "label": "unsure", "confidence": None} for r in unlabelled}
    write_output(predictions.values(), claims, out)
    log("wrote the first complete table")

    status = 0
    try:
        pipeline = Pipeline(practice, lexicon, engine)
    except Exception:
        log("engine unavailable; every unlabelled row stays unsure")
        traceback.print_exc()
        return 1

    def keep(p):
        predictions[p["id"]] = {"id": p["id"], "label": p.get("label") or "unsure", "confidence": p.get("confidence")}

    errors, done, last_write = 0, 0, time.time()
    # The batch first: it sees the whole input. If it fails, the same engine row by row.
    try:
        batch = pipeline.label_all(rows) if deadline is None or time.time() < deadline else None
        if batch is not None:
            for p in batch:
                if p.get("id") in predictions:
                    keep(p)
            done = len(unlabelled)
            log(f"batch: {len(batch)} rows labelled with page context and corroboration")
    except Stop:
        log("SIGTERM during the batch: the first table stands")
        return 0
    except Exception:
        log("batch failed; labelling row by row with the same engine")
        traceback.print_exc()
    try:
        for row in unlabelled if done == 0 else []:
            if deadline is not None and time.time() > deadline:
                log("deadline near: stopping classification")
                break
            try:
                keep({**pipeline.predict(row), "id": row["id"]})
            except Exception:
                errors += 1
                if errors <= 5:
                    traceback.print_exc()
            done += 1
            if time.time() - last_write > REWRITE_EVERY_S:
                write_output(predictions.values(), claims, out)
                last_write = time.time()
                log(f"classified {done}/{len(unlabelled)}")
    except Stop:
        log("SIGTERM: writing what is classified")
        status = 0
    write_output(predictions.values(), claims, out)
    counts = {}
    for p in predictions.values():
        counts[p["label"]] = counts.get(p["label"], 0) + 1
    log(f"final table: {done}/{len(unlabelled)} classified, {errors} errors, labels {counts}, {len(claims)} claims")
    return status


def main():
    signal.signal(signal.SIGTERM, _on_sigterm)
    return run(
        os.environ.get("ARENA_UNIVERSE", "/universe"),
        os.environ.get("ARENA_OUTPUT", "/output"),
        os.environ.get("ARENA_PRACTICE", os.path.join(HERE, "data", "practice.csv")),
        deadline=deadline_from_env(),
    )


if __name__ == "__main__":
    sys.exit(main())
