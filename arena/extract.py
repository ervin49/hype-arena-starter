"""Text -> facts.

build_extractor(practice_rows, lexicon) -> Extractor
extract(row, lexicon, extractor, context=None) -> {"facts", "complete", "issues", "scores"}
extract_batch(rows, lexicon, extractor) -> [extraction]   (rows in input order)

Each value the text writes (arena.values) becomes a candidate fact. Its
subject is a name the sentence holds, or, for "It costs €59 a month", a
subject of the rows just before it on the same page. Its attribute is the
subject's lexicon attribute that best explains the words around the value,
by a naive Bayes model trained on the practice forms, constrained by the
value's kind and unit. A value that fits no attribute well is not a fact
(class NONE, also learned from practice). Yes-or-no facts have no span:
they come from the attribute's words and the sentence's polarity.
"""

import json
import math
import re
from collections import Counter, defaultdict

from arena.lexicon import Lexicon
from arena.values import has_negation, norm_name, parse_values, singular, values_equal

NONE = "<none>"
_WORD = re.compile(r"[a-z][a-z0-9']*")
_STOP = {"the", "a", "an", "of", "and", "to", "in", "is", "for", "on", "at", "it", "its",
         "with", "by", "as", "that", "this", "we", "our", "are", "be", "has", "from"}
CONTEXT_ROWS = 6
FALLBACK_PRIOR = -4.0


def _tokens(text):
    return [singular(w) for w in _WORD.findall(text.lower()) if w not in _STOP]


def _attr_words(attribute):
    return [singular(w) for w in attribute.split("_") if w and w not in _STOP]


class NaiveBayes:
    """Multinomial naive Bayes with add-alpha smoothing over string features."""

    def __init__(self, alpha=0.3):
        self.alpha = alpha
        self.fc = defaultdict(Counter)
        self.total = Counter()
        self.cc = Counter()
        self.vocab = set()

    def add(self, cls, feats):
        self.cc[cls] += 1
        for f in feats:
            self.fc[cls][f] += 1
            self.total[cls] += 1
            self.vocab.add(f)

    def loglik(self, cls, feats):
        v = len(self.vocab) + 1
        t = self.total[cls] + self.alpha * v
        fc = self.fc[cls]
        return sum(math.log((fc.get(f, 0) + self.alpha) / t) for f in feats if f in self.vocab)


class Extractor:
    def __init__(self, lexicon_obj):
        self.lex = lexicon_obj
        self.nb = NaiveBayes()          # value facts: class = attribute or NONE
        self.nb_bool = NaiveBayes()     # yes or no facts: class = attribute or NONE
        self.attr_kinds = defaultdict(Counter)      # attribute -> kinds
        self.sa_units = defaultdict(Counter)        # (subject, attribute) -> units
        self.attr_units = defaultdict(Counter)      # attribute -> units
        self.sa_count = Counter()                   # (subject, attribute) -> facts
        self.subj_count = Counter()
        self.known_forms = {}                       # row id -> facts (practice)
        self.text_forms = {}                        # normalised text -> facts
        self.recent = []                            # (date, [subjects]) of recent rows
        self.bool_none_rate = 0.0
        self.none_bias = -4.0   # tuned with eval/eval_extract.py
        self.bool_bias = 0.0


def _value_feats(text, span, kind, value):
    toks_before = _tokens(text[max(0, span["start"] - 60):span["start"]])[-5:]
    toks_after = _tokens(text[span["end"]:span["end"] + 60])[:5]
    f = ["k:" + kind]
    if kind == "name":
        f += ["nv:" + norm_name(value["value"]), "nm:" + ("subj" if span.get("name") else "val")] * 2
    unit = value.get("unit")
    if unit:
        f.append("u:" + singular(str(unit)))
    if value.get("per"):
        f.append("per:" + value["per"])
    if value.get("currency"):
        f.append("cur:" + value["currency"])
    f += ["b:" + w for w in toks_before] + ["a:" + w for w in toks_after]
    f += ["l:" + w for w in toks_before[-2:] + toks_after[:2]] * 2
    return f


def _masked(text, spans):
    out = text
    for s, e in sorted(spans, reverse=True):
        out = out[:s] + " " + out[e:]
    return out


def _row_feats(text, mention_spans):
    toks = _tokens(_masked(text, mention_spans))
    bigr = [a + "_" + b for a, b in zip(toks, toks[1:])]
    return ["w:" + t for t in toks] + ["g:" + b for b in bigr]


def _name_spans(lex, text):
    return lex.mentions(text)


def build_extractor(practice_rows, lexicon):
    value_names = set()
    rows = []
    for r in practice_rows:
        form = r.get("form")
        if not form:
            continue
        facts = json.loads(form) if isinstance(form, str) else form
        rows.append((r, facts))
        for f in facts:
            if f["value"].get("kind") == "name":
                value_names.add(f["value"]["value"])
    lex = Lexicon(lexicon, value_names)
    ex = Extractor(lex)
    bool_rows = none_rows = 0
    for r, facts in rows:
        text = r["text"]
        ex.known_forms[r["id"]] = facts
        ex.text_forms.setdefault(norm_name(text), facts)
        mentions = lex.mentions(text)
        spans = parse_values(text, [(m["start"], m["end"]) for m in mentions if m["is_subject"]])
        rowf = _row_feats(text, [(m["start"], m["end"]) for m in mentions])
        for f in facts:
            a, v = f["attribute"], f["value"]
            ex.attr_kinds[a][v["kind"]] += 1
            ex.sa_count[(f["subject"], a)] += 1
            ex.subj_count[f["subject"]] += 1
            if v.get("unit"):
                ex.sa_units[(f["subject"], a)][singular(str(v["unit"]))] += 1
                ex.attr_units[a][singular(str(v["unit"]))] += 1
        used = set()
        for f in facts:
            v = f["value"]
            if v["kind"] == "boolean":
                continue
            cands = _value_candidates(lex, text, spans, mentions)
            for i, (span, val) in enumerate(cands):
                if i in used:
                    continue
                if val["kind"] == v["kind"] and values_equal(
                        {k: x for k, x in val.items() if k != "op"},
                        {k: x for k, x in v.items() if k != "op"}):
                    used.add(i)
                    ex.nb.add(f["attribute"], _value_feats(text, span, val["kind"], val) + rowf)
                    break
        for i, (span, val) in enumerate(_value_candidates(lex, text, spans, mentions)):
            if i not in used:
                ex.nb.add(NONE + val["kind"], _value_feats(text, span, val["kind"], val) + rowf)
        bools = [f for f in facts if f["value"]["kind"] == "boolean"]
        for f in bools:
            ex.nb_bool.add(f["attribute"], rowf)
            bool_rows += 1
        if not bools:
            ex.nb_bool.add(NONE, rowf)
            none_rows += 1
    ex.bool_none_rate = none_rows / max(1, none_rows + bool_rows)
    return ex


def _value_candidates(lex, text, spans, mentions):
    """(span, value) pairs: parsed values plus names that could be values."""
    out = [(s, s["value"]) for s in spans]
    for m in mentions:
        out.append(({"start": m["start"], "end": m["end"], "raw": m["surface"],
                     "negated": False, "approx": False, "range": False, "name": m["name"]},
                    {"kind": "name", "value": m["surface"] if not m["is_subject"] else m["name"]}))
    return out


def _unit_ok(ex, subject, attribute, value):
    kind = value["kind"]
    kinds = ex.attr_kinds.get(attribute)
    if kinds and kind not in kinds:
        return False
    if not kinds:
        # an attribute the practice never shows: allow it only weakly, by name
        return None
    if kind == "quantity":
        u = singular(str(value.get("unit")))
        units = ex.sa_units.get((subject, attribute)) or ex.attr_units.get(attribute)
        if units and u not in units:
            from arena.values import UNIT_BASE
            dims = {UNIT_BASE[x][0] for x in units if x in UNIT_BASE}
            if not (value.get("unit") in UNIT_BASE and UNIT_BASE[value["unit"]][0] in dims):
                return False
    return True


def _context_subjects(ex, row, context):
    if context is not None:
        return context
    out = []
    for d, subs in reversed(ex.recent):
        if d != row.get("date"):
            break
        for s in subs:
            if s not in out:
                out.append(s)
    return out


def remember(ex, row, facts, text=None):
    """Record a row's subjects as context for the rows after it: those of
    its facts first, then the other subjects it names."""
    subs = []
    for f in facts:
        if f["subject"] not in subs:
            subs.append(f["subject"])
    for m in ex.lex.mentions(text or row.get("text") or ""):
        if m["is_subject"] and m["name"] not in subs:
            subs.append(m["name"])
    ex.recent.append((row.get("date"), subs))
    del ex.recent[:-CONTEXT_ROWS]


def extract(row, lexicon, extractor, context=None, remember_row=True):
    ex, lex = extractor, extractor.lex
    text = row.get("text") or ""
    issues = []
    mentions = lex.mentions(text)
    subj_mentions = [m for m in mentions if m["is_subject"]]
    spans = parse_values(text, [(m["start"], m["end"]) for m in subj_mentions])
    rowf = _row_feats(text, [(m["start"], m["end"]) for m in mentions])
    ctx = _context_subjects(ex, row, context)

    # subject candidates with a prior (log scale)
    def subject_prior(subject, pos):
        # the nearest mention before the value is the likeliest subject
        before = [m for m in subj_mentions if m["end"] <= pos]
        nearest = before[-1]["name"] if before else None
        if subject == nearest:
            return 0.0
        if any(m["name"] == subject for m in subj_mentions):
            after = [m for m in subj_mentions if m["start"] >= pos]
            return -0.8 if after and after[0]["name"] == subject and not before else -1.6
        if subject in ctx:
            return -1.2 - 0.6 * ctx.index(subject)
        return FALLBACK_PRIOR

    cand_subjects = []
    for m in subj_mentions:
        if m["name"] not in cand_subjects:
            cand_subjects.append(m["name"])
    for s in ctx:
        if s not in cand_subjects:
            cand_subjects.append(s)
    if not cand_subjects:
        issues.append("no subject")
    # any subject, at a cost: "5 regions." names no subject at all
    for s in ex.subj_count:
        if s not in cand_subjects and s in lex.subjects:
            cand_subjects.append(s)

    facts, scores, used_spans = [], [], []
    taken = set()
    cands = _value_candidates(lex, text, spans, mentions)
    # alternative readings of one span ("4.5 stars" or version 4.5) compete
    for span, val in cands:
        if span.get("approx") or span.get("range"):
            issues.append(f"approximate or range value: {span['raw']}")
            continue
        best = None
        feats = _value_feats(text, span, val["kind"], val) + rowf
        none_cls = NONE + val["kind"]
        none_score = math.log(ex.nb.cc[none_cls] + 1) + ex.nb.loglik(none_cls, feats) + ex.none_bias
        for subject in cand_subjects:
            if val["kind"] == "name" and span.get("name") == subject:
                continue
            sp = subject_prior(subject, span["start"])
            if sp is None:
                continue
            for a in lex.attributes(subject):
                ok = _unit_ok(ex, subject, a, val)
                if ok is False:
                    continue
                prior = math.log(ex.sa_count.get((subject, a), 0) + 0.5) - math.log(ex.subj_count.get(subject, 0) + 1)
                s = sp + prior + math.log(ex.nb.cc.get(a, 0) + 1) + ex.nb.loglik(a, feats)
                words = _attr_words(a)
                near = set(_tokens(text))
                s += 1.5 * sum(w in near for w in words) / max(1, len(words))
                if ok is None:
                    s -= 4.0
                if best is None or s > best[0]:
                    best = (s, subject, a)
        if best is None:
            continue
        margin = best[0] - none_score
        if margin < 0:
            continue
        v = dict(val)
        if v["kind"] == "name":
            v["value"] = lex.resolve_value_name(v["value"]) or v["value"]
        fact = {"subject": best[1], "attribute": best[2], "value": v}
        key = (best[1], best[2], span["start"])
        if key in taken:
            continue
        if span.get("negated") and v["kind"] != "name":
            issues.append(f"negated value: {span['raw']}")
        # the same span read twice (alternatives): keep the stronger
        clash = [i for i, (fs, sp_) in enumerate(zip(facts, used_spans)) if sp_[0] < span["end"] and span["start"] < sp_[1]]
        if clash:
            i = clash[0]
            if scores[i] >= margin:
                continue
            facts.pop(i), scores.pop(i), used_spans.pop(i)
        taken.add(key)
        facts.append(fact)
        scores.append(margin)
        used_spans.append((span["start"], span["end"]))

    # yes-or-no facts
    bool_attrs = []
    for subject in cand_subjects:
        sp = subject_prior(subject, 0 if not subj_mentions else subj_mentions[0]["end"])
        if sp is None or sp <= FALLBACK_PRIOR:
            continue
        for a in lex.attributes(subject):
            kinds = ex.attr_kinds.get(a)
            if kinds and "boolean" not in kinds:
                continue
            if not kinds and not any(w in _tokens(text) for w in _attr_words(a)):
                continue
            prior = math.log(ex.sa_count.get((subject, a), 0) + 0.5) - math.log(ex.subj_count.get(subject, 0) + 1)
            s = sp + prior + math.log(ex.nb_bool.cc.get(a, 0) + 1) + ex.nb_bool.loglik(a, rowf)
            words = _attr_words(a)
            s += 2.0 * sum(w in _tokens(text) for w in words) / max(1, len(words))
            bool_attrs.append((s, subject, a))
    if bool_attrs:
        none_b = math.log(ex.nb_bool.cc[NONE] + 1) + ex.nb_bool.loglik(NONE, rowf)
        s, subject, a = max(bool_attrs)
        margin = s - none_b - ex.bool_bias
        if margin > (2.0 if facts else 0.0):
            facts.append({"subject": subject, "attribute": a,
                          "value": {"kind": "boolean", "value": not has_negation(text)}})
            scores.append(margin)

    complete = bool(facts)
    if not facts:
        issues.append("no fact extracted")
    if any(sc < 1.0 for sc in scores):
        issues.append("weak attribute match")
    if facts and all(f["subject"] not in [m["name"] for m in subj_mentions] for f in facts):
        issues.append("subject from context")
    if remember_row:
        remember(ex, row, facts)
    return {"facts": facts, "complete": complete, "issues": issues, "scores": [round(s, 3) for s in scores]}


def extract_batch(rows, lexicon, extractor):
    """Extract every row in input order. Rows the practice data holds (by id,
    with a form) give their known facts as context instead of extractions."""
    out = []
    extractor.recent = []
    for r in rows:
        known = extractor.known_forms.get(r.get("id")) if r.get("label") else None
        if known is not None:
            remember(extractor, r, known)
            out.append({"facts": known, "complete": True, "issues": ["known form"], "scores": []})
        else:
            out.append(extract(r, lexicon, extractor))
    return out
