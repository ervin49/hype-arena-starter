"""Batch runner: /universe in, /output/output.csv out.

Order of work, so that a complete table is on disk as early as possible:
1. read the input, generate and validate the claims;
2. write a first complete table: the claims, and every unlabelled row unsure;
3. classify the unlabelled rows with the engine, rewriting the table now and then;
4. the controls (arena.controls): lower the confidence as far as a held-out control group
   shows it is over-stated, and veto claims that rows the engine is sure of contradict;
5. write the final table. Every write is atomic (arena.io.write_output).
"""
import csv
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
CLAIMS_FALLBACK = os.path.join(HERE, "data", "claims_fallback.csv")
REWRITE_EVERY_S = 60
ERROR_CONFIDENCE = 0.8  # the engine's answer for a row with no facts read: true at the base rate
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


def run_controls(pipeline, rows, practice, all_practice, lexicon, batch, predictions, claims, claims_target, deadline):
    """The controls of arena.controls, each on its own: one that fails or runs out of time is
    skipped and leaves the table as it was. Returns the claims to write."""
    from arena import controls
    from arena.generate import select_claims

    def time_left():
        return deadline is None or time.time() < deadline

    control = controls.load_control()
    if control is None:
        log("confidence control: no control model; confidence unchanged")
    elif time_left():
        try:
            ids, m1, m2 = control
            hidden, practice_out, group, _ = controls.control_input(rows, practice, ids)
            members = set(group)
            answers = pipeline.engine.label_rows(hidden, practice_out, lexicon, models=(m1, m2))
            truth = {r["id"]: r["label"] for r in rows if r["id"] in members}
            factors, report = controls.measure([p for p in answers if p.get("id") in members], truth)
            controls.apply(predictions, factors)
            log(f"confidence control: {len(members)} held-out rows; {report}")
            labels = [p["label"] for p in predictions.values() if p["label"] in ("true", "false")]
            if labels and "false_share" in report:
                share = sum(lab == "false" for lab in labels) / len(labels)
                log(f"distribution monitor: false share {share:.3f} on the input, "
                    f"{report['false_share']:.3f} on the control group")
        except Stop:
            raise
        except Exception:
            log("confidence control failed; confidence unchanged")
            traceback.print_exc()
    if time_left():
        try:
            check = controls.check_rows(rows, batch)
            checked, report = select_claims(all_practice, lexicon, AS_OF, [r["text"] for r in rows],
                                            claims_target, check_rows=check)
            log(f"claim control: {len(check)} confident input rows as evidence; vetoed "
                f"{report.get('vetoed_by_input', 0)} candidates, {report.get('vetoed_but_needed', 0)} still needed")
            if len(checked) >= len(claims):
                return checked
            log("claim control: fewer claims than before; keeping the first set")
        except Stop:
            raise
        except Exception:
            log("claim control failed; the first claims stand")
            traceback.print_exc()
    return claims


class Stop(Exception):
    pass


def _on_sigterm(signum, frame):
    raise Stop()


def load_lexicon(universe_dir):
    """The input's lexicon; the image's own (data/lexicon.json) if the input's can't be read,
    since a lexicon the loader refuses would otherwise cost the whole output. Events are kept
    as names: an object with a name counts, anything else is dropped."""
    try:
        lexicon = read_lexicon(os.path.join(universe_dir, "lexicon.json"))
    except Exception:
        log("the input lexicon is unreadable; using the image's data/lexicon.json")
        traceback.print_exc()
        lexicon = read_lexicon(os.path.join(HERE, "data", "lexicon.json"))
    events = lexicon.get("events") if isinstance(lexicon.get("events"), list) else []
    lexicon["events"] = [e["name"] if isinstance(e, dict) else e for e in events
                         if isinstance(e, str) or (isinstance(e, dict) and isinstance(e.get("name"), str))]
    return lexicon


def read_claims_fallback(path):
    """The claims of data/claims_fallback.csv (scripts/claims_fallback.py), for a run whose
    claim generation fails: the output.csv rows with a type, form kept as its JSON string."""
    with open(path, encoding="utf-8", newline="") as f:
        return [{"id": r["id"], "type": r["type"], "text": r["text"], "form": r["form"],
                 "label": "true", "confidence": float(r["confidence"])}
                for r in csv.DictReader(f) if r.get("type")]


def run(universe_dir, output_dir, practice_path, engine=None, deadline=None, claims_target=CLAIMS):
    out = os.path.join(output_dir, "output.csv")
    repairs = []
    rows = read_rows(os.path.join(universe_dir, "universe.csv"), lenient=True, repairs=repairs)
    if repairs:
        log(f"{len(repairs)} rows repaired or dropped; first: {'; '.join(repairs[:5])}")
    lexicon = load_lexicon(universe_dir)
    labelled, unlabelled = split_rows(rows)
    # A table exists before anything else can fail: every unlabelled row unsure, no claims yet.
    predictions = {r["id"]: {"id": r["id"], "label": "unsure", "confidence": None} for r in unlabelled}
    write_output(predictions.values(), [], out)
    log("wrote the first table (no claims yet)")
    all_practice = read_rows(practice_path, require_form=True)
    practice = known_practice(all_practice, rows)
    log(f"input: {len(rows)} rows, {len(unlabelled)} unlabelled; practice with forms: "
        f"{len(all_practice)}, of which the engine sees {len(practice)}")

    # Claims come from the whole practice file, as in the real run where every practice
    # row is labelled; the engine sees only the labels the input shows (no leakage into labels).
    try:
        from arena.generate import select_claims
        claims, report = select_claims(all_practice, lexicon, AS_OF, [r["text"] for r in rows], claims_target)
        log(f"claims: {len(claims)} selected; {report}")
    except Exception:
        log("claim generation failed; using data/claims_fallback.csv")
        traceback.print_exc()
        claims = read_claims_fallback(CLAIMS_FALLBACK)[:claims_target]
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
    batch = None
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
                # as for a row the engine can't read: true at the base rate, never unsure
                keep({"id": row["id"], "label": "true", "confidence": ERROR_CONFIDENCE})
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
    if batch is not None:
        try:
            claims = run_controls(pipeline, rows, practice, all_practice, lexicon, batch, predictions, claims,
                                  claims_target, deadline)
            write_output(predictions.values(), claims, out)
        except Stop:
            log("SIGTERM during the controls: the table without them stands")
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
