"""Facts and their checks -> a label for the row.

classify(row, extraction, check) -> {"id", "label", "confidence", "evidence_ids", "reason"}

check(fact, date) -> the result of arena.truth.check_fact. The row is false
when one well-extracted fact is contradicted, true when every fact is
supported and the extraction is complete, and unsure otherwise. The reason
keeps apart "unknown in the universe" and "not understood by the extractor":
they have different remedies, though both export as unsure.
"""

import os

from arena.ml.model import PASS2_PATH, decide, featurize, load_model

# An extraction weaker than this (naive Bayes margin, log scale) does not
# decide a label on its own.
MIN_FACT_SCORE = 0.0
MIN_CONFIDENCE = 0.5
# A firm label whose probability is below this becomes unsure. 0 keeps every
# label firm; the team sets the policy once the scoring is known.
UNSURE_BELOW = float(os.environ.get("ARENA_UNSURE_BELOW", "0") or 0)

# Self-training: a second pass re-checks every row against the evidence plus
# what the first pass is confident about (arena/ml/model_pass2.json).
PSEUDO_TAU = 0.85

_MODEL = load_model()
_MODEL_PASS2 = load_model(PASS2_PATH)


def _fact_text(f):
    v = f["value"]
    shown = v.get("value")
    if v.get("unit"):
        shown = f"{shown} {v['unit']}"
    if v.get("currency"):
        shown = f"{v['currency']} {shown}" + (f"/{v['per']}" if v.get("per") else "")
    return f"{f['subject']} {f['attribute']} = {shown}"


def classify(row, extraction, check, model="default"):
    """The label of a row. With the trained model (arena/ml/model.json) the
    label and confidence come from it, the reason from the rules; without
    it, from the rules alone."""
    model = _MODEL if model == "default" else model
    pred = classify_rules(row, extraction, check)
    if model is None:
        return pred
    checks = pred.pop("_raw_checks")
    probs = model.probs(featurize(row, extraction, checks))
    label, conf = decide(probs, UNSURE_BELOW)
    if label != pred["label"]:
        pred["reason"] = (f"Model: {label} ({probs[label]:.2f}) on the evidence; "
                          f"the rules alone say {pred['label']}. " + pred["reason"])
    pred.update(label=label, confidence=conf, probs={k: round(v, 3) for k, v in probs.items()})
    return pred


def classify_rules(row, extraction, check):
    facts = extraction.get("facts") or []
    scores = extraction.get("scores") or [None] * len(facts)
    rid = row.get("id")
    if not facts:
        return {"id": rid, "label": "unsure", "confidence": None, "evidence_ids": [],
                "reason": "Not understood: no fact extracted.", "kind": "not_understood",
                "checks": [], "_raw_checks": []}
    checks = [check(f, row["date"]) for f in facts]
    detail = [dict(c, fact=_fact_text(f)) for f, c in zip(facts, checks)]
    evidence = []
    for c in checks:
        for e in c.get("evidence_ids", []):
            if e not in evidence:
                evidence.append(e)

    def strong(i):
        s = scores[i] if i < len(scores) else None
        return s is None or s >= MIN_FACT_SCORE

    contra = [i for i, c in enumerate(checks) if c["status"] == "contradicted" and strong(i)]
    if contra:
        i = max(contra, key=lambda j: checks[j]["confidence"] or 0)
        conf = max(MIN_CONFIDENCE, min(1.0, checks[i]["confidence"] or MIN_CONFIDENCE))
        return {"id": rid, "label": "false", "confidence": round(conf, 3),
                "evidence_ids": checks[i]["evidence_ids"],
                "reason": f"Contradicted: {_fact_text(facts[i])}. {checks[i]['reason']}",
                "kind": "contradicted", "checks": detail, "_raw_checks": checks}
    if extraction.get("complete") and all(c["status"] == "supported" for c in checks):
        conf = 1.0
        for c in checks:
            conf *= c["confidence"] or MIN_CONFIDENCE
        conf = max(MIN_CONFIDENCE, min(1.0, conf))
        return {"id": rid, "label": "true", "confidence": round(conf, 3),
                "evidence_ids": evidence,
                "reason": "Supported: " + "; ".join(c["reason"] for c in checks),
                "kind": "supported", "checks": detail, "_raw_checks": checks}
    unknown = [c for c in checks if c["status"] == "unknown"]
    why = ("Unknown in the universe: " + unknown[0]["reason"]) if unknown else \
        "Not understood: the extraction is incomplete."
    return {"id": rid, "label": "unsure", "confidence": None, "evidence_ids": evidence,
            "reason": why, "kind": "unknown" if unknown else "not_understood",
            "checks": detail, "_raw_checks": checks}


def label_rows(rows, practice_rows, lexicon, kb=None, extractor=None, self_train=True):
    """The whole engine on an input: [prediction] for every unlabelled row.

    rows: the universe in input order (labelled rows give context and
    corroboration; only unlabelled rows are classified). Each prediction
    also holds "extraction" for display.

    With self_train and a pass-2 model, a second pass checks each row
    against the evidence plus the rows the first pass is confident about,
    leaving out the row's own page."""
    from arena.extract import build_extractor, extract_batch
    from arena.truth import build_kb, check_fact, page_groups
    kb = kb or build_kb(practice_rows, lexicon)
    extractor = extractor or build_extractor(practice_rows, lexicon)
    exs = extract_batch(rows, lexicon, extractor)
    kb.unl.clear()
    kb.add_statements(rows, exs)
    check = lambda fact, date: check_fact(fact, date, kb)
    todo = [(r, ex) for r, ex in zip(rows, exs) if not (r.get("label") or "").strip()]
    out = []
    for r, ex in todo:
        p = classify(r, ex, check)
        p["extraction"] = ex
        out.append(p)
    if not (self_train and _MODEL_PASS2 and out):
        return out
    kb2 = kb.with_pseudo([r for r, _ in todo], [ex for _, ex in todo],
                         [p.get("probs") for p in out], PSEUDO_TAU)
    page = page_groups(rows)
    out2 = []
    for (r, ex), first in zip(todo, out):
        own = page[r["id"]]
        p = classify(r, ex, lambda fact, date: check_fact(fact, date, kb2, own), model=_MODEL_PASS2)
        p["extraction"] = ex
        p["first_pass"] = {"label": first["label"], "confidence": first["confidence"]}
        out2.append(p)
    return out2
