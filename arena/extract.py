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
FALLBACK_PRIOR = -11.0
# Strength of the naive Bayes prior toward all facts' words; a broad optimum
# (300 to 2,000) in eval/eval_extract.py's page-grouped CV.
NB_PRIOR = 1000.0


def _tokens(text):
    return [singular(w) for w in _WORD.findall(text.lower()) if w not in _STOP]


def _attr_words(attribute):
    return [singular(w) for w in attribute.split("_") if w and w not in _STOP]


class NaiveBayes:
    """Multinomial naive Bayes over string features.

    A class's word distribution is smoothed toward the pooled distribution
    of every fact class (a Dirichlet prior of strength `prior`), not toward
    uniform: an attribute with one or two practice examples then reads like
    a fact in general, and its name words and units tell it apart. With
    prior 0 it is plain add-alpha smoothing."""

    def __init__(self, alpha=0.3, prior=0.0):
        self.alpha, self.prior = alpha, prior
        self.fc = defaultdict(Counter)
        self.total = Counter()
        self.cc = Counter()
        self.vocab = set()
        self.pooled, self.pooled_total = Counter(), 0

    def add(self, cls, feats):
        self.cc[cls] += 1
        for f in feats:
            self.fc[cls][f] += 1
            self.total[cls] += 1
            self.vocab.add(f)
            if not cls.startswith(NONE):
                self.pooled[f] += 1
                self.pooled_total += 1

    def loglik(self, cls, feats):
        v = len(self.vocab) + 1
        fc = self.fc[cls]
        if not self.prior or cls.startswith(NONE):
            t = self.total[cls] + self.alpha * v
            return sum(math.log((fc.get(f, 0) + self.alpha) / t) for f in feats if f in self.vocab)
        pt = self.pooled_total + self.alpha * v
        t = self.total[cls] + self.prior
        return sum(math.log((fc.get(f, 0) + self.prior * (self.pooled.get(f, 0) + self.alpha) / pt) / t)
                   for f in feats if f in self.vocab)


class Extractor:
    def __init__(self, lexicon_obj):
        self.lex = lexicon_obj
        self.nb = NaiveBayes(prior=NB_PRIOR)        # value facts, words near the value: class = attribute or NONE+kind
        self.nb_row = NaiveBayes(prior=NB_PRIOR)    # value facts, words of the whole row
        self.row_weight = 0.4           # weight of the row model against the local one
        self.name_values = set()        # normalised names seen as values in practice
        self.kind_facts = Counter()     # value kind -> facts of that kind in practice
        self.ctx_prior, self.ctx_step = -4.0, 0.6   # log prior of a subject from context
        self.fallback_prior = FALLBACK_PRIOR       # of a subject the page never names
        self.nb_bool = NaiveBayes(prior=NB_PRIOR)   # yes or no facts: class = attribute or NONE
        self.attr_kinds = defaultdict(Counter)      # attribute -> kinds
        self.sa_units = defaultdict(Counter)        # (subject, attribute) -> units
        self.attr_units = defaultdict(Counter)      # attribute -> units
        self.sa_count = Counter()                   # (subject, attribute) -> facts
        self.subj_count = Counter()
        self.known_forms = {}                       # row id -> facts (practice)
        self.recent = []                            # (date, [subjects]) of recent rows
        self.none_bias = -7.0   # tuned with eval/eval_extract.py (page-grouped CV)
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
    ex.name_values = {norm_name(n) for n in value_names}
    for r, facts in rows:
        text = r["text"]
        ex.known_forms[r["id"]] = facts
        mentions = lex.mentions(text)
        spans = parse_values(text, [(m["start"], m["end"]) for m in mentions if m["is_subject"]])
        rowf = _row_feats(text, [(m["start"], m["end"]) for m in mentions])
        for f in facts:
            a, v = f["attribute"], f["value"]
            ex.attr_kinds[a][v["kind"]] += 1
            ex.sa_count[(f["subject"], a)] += 1
            ex.subj_count[f["subject"]] += 1
            ex.kind_facts[v["kind"]] += 1
            if v.get("unit"):
                ex.sa_units[(f["subject"], a)][singular(str(v["unit"]))] += 1
                ex.attr_units[a][singular(str(v["unit"]))] += 1
        used = set()
        for f in facts:
            v = f["value"]
            if v["kind"] == "boolean":
                continue
            cands = _value_candidates(lex, text, spans, mentions, ex.name_values)
            for i, (span, val) in enumerate(cands):
                if i in used:
                    continue
                if val["kind"] == v["kind"] and values_equal(
                        {k: x for k, x in val.items() if k != "op"},
                        {k: x for k, x in v.items() if k != "op"}):
                    used.add(i)
                    ex.nb.add(f["attribute"], _value_feats(text, span, val["kind"], val))
                    ex.nb_row.add(f["attribute"], rowf)
                    break
        for i, (span, val) in enumerate(_value_candidates(lex, text, spans, mentions, ex.name_values)):
            if i not in used:
                ex.nb.add(NONE + val["kind"], _value_feats(text, span, val["kind"], val))
                ex.nb_row.add(NONE + val["kind"], rowf)
        bools = [f for f in facts if f["value"]["kind"] == "boolean"]
        for f in bools:
            ex.nb_bool.add(f["attribute"], rowf)
        if not bools:
            ex.nb_bool.add(NONE, rowf)
    return ex


def _value_candidates(lex, text, spans, mentions, name_values):
    """(span, value) pairs: parsed values plus names that could be values:
    names that are no subject, and subjects named as values in practice
    (people such as Erlich Bachmann), not products or events."""
    out = [(s, s["value"]) for s in spans]
    for m in mentions:
        if m["is_subject"] and norm_name(m["name"]) not in name_values:
            continue
        out.append(({"start": m["start"], "end": m["end"], "raw": m["surface"],
                     "negated": False, "approx": False, "range": False, "name": m["name"]},
                    {"kind": "name", "value": m["surface"] if not m["is_subject"] else m["name"]}))
    return out


def _attr_prior(ex, lex, subject, attribute):
    """log P(attribute | subject), smoothed over the subject's attributes."""
    n_attrs = max(1, len(lex.attributes(subject)))
    return math.log((ex.sa_count.get((subject, attribute), 0) + 0.5)
                    / (ex.subj_count.get(subject, 0) + 0.5 * n_attrs))


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
            return ex.ctx_prior - ex.ctx_step * ctx.index(subject)
        return ex.fallback_prior

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

    # Score every reading of every value against every (subject, attribute),
    # then assign greedily, strongest first: one value per span, and one
    # value per (subject, attribute) in a row.
    options = []
    near = set(_tokens(text))
    cands = _value_candidates(lex, text, spans, mentions, ex.name_values)
    for ci, (span, val) in enumerate(cands):
        if span.get("approx") or span.get("range"):
            issues.append(f"approximate or range value: {span['raw']}")
            continue
        feats = _value_feats(text, span, val["kind"], val)
        none_cls = NONE + val["kind"]
        n_none = ex.nb.cc[none_cls] + 1
        n_fact = ex.kind_facts[val["kind"]] + 1
        p_none = math.log(n_none / (n_none + n_fact))
        none_score = (p_none + ex.nb.loglik(none_cls, feats)
                      + ex.row_weight * ex.nb_row.loglik(none_cls, rowf) + ex.none_bias)
        p_fact = math.log(n_fact / (n_none + n_fact))
        for subject in cand_subjects:
            if val["kind"] == "name" and span.get("name") == subject:
                continue
            sp = subject_prior(subject, span["start"])
            for a in lex.attributes(subject):
                ok = _unit_ok(ex, subject, a, val)
                if ok is False:
                    continue
                sc = (p_fact + sp + _attr_prior(ex, lex, subject, a) + ex.nb.loglik(a, feats)
                      + ex.row_weight * ex.nb_row.loglik(a, rowf))
                words = _attr_words(a)
                sc += 1.5 * sum(w in near for w in words) / max(1, len(words))
                if ok is None:
                    sc -= 4.0
                if sc > none_score:
                    options.append((sc - none_score, ci, subject, a))
    options.sort(key=lambda o: -o[0])
    facts, scores, chosen = [], [], []
    used_sa = set()
    for margin, ci, subject, a in options:
        span, val = cands[ci]
        if any(cs < span["end"] and span["start"] < ce for cs, ce in chosen):
            continue
        if (subject, a) in used_sa:
            continue
        v = dict(val)
        if v["kind"] == "name":
            v["value"] = lex.resolve_value_name(v["value"]) or v["value"]
        fact = {"subject": subject, "attribute": a, "value": v}
        if span.get("negated") and v["kind"] != "name":
            issues.append(f"negated value: {span['raw']}")
            fact["negated"] = True      # "does not cost €59": the check is inverted
        facts.append(fact)
        scores.append(margin)
        chosen.append((span["start"], span["end"]))
        used_sa.add((subject, a))
    order = sorted(range(len(facts)), key=lambda i: chosen[i][0])
    facts, scores = [facts[i] for i in order], [scores[i] for i in order]

    # yes-or-no facts
    bool_attrs = []
    for subject in cand_subjects:
        sp = subject_prior(subject, 0 if not subj_mentions else subj_mentions[0]["end"])
        if sp is None or sp <= ex.fallback_prior:
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

    # where each fact's subject comes from: named in the sentence, the page's
    # context, or neither (a guess the classifier should trust less)
    named = {m["name"] for m in subj_mentions}
    origin = ["named" if f["subject"] in named else "context" if f["subject"] in ctx else "other"
              for f in facts]
    complete = bool(facts)
    if not facts:
        issues.append("no fact extracted")
    if any(sc < 1.0 for sc in scores):
        issues.append("weak attribute match")
    if facts and all(f["subject"] not in [m["name"] for m in subj_mentions] for f in facts):
        issues.append("subject from context")
    if remember_row:
        remember(ex, row, facts)
    return {"facts": facts, "complete": complete, "issues": issues, "scores": [round(s, 3) for s in scores],
            "subject_from": origin}


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
