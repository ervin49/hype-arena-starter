"""Strict checks on a generated claim, before it may enter output.csv.

validate_claim(claim, practice_rows, lexicon, input_texts) -> {"valid": bool, "issues": [str]}

1. The entry against contracts/entry.schema.json (label -> tag).
2. Names and attributes against the lexicon.
3. The text against contracts/claim-forms.md: one sentence, the subject named, the
   value read back by the engine's independent parser (arena.values), no other
   value of its kind, no date or time word of its own, no negation, the phrases
   each type needs.
4. The evidence: practice rows labelled true that state the claim's facts.
5. Id, length, and novelty against every input text.

"Valid" means supported by our evidence and readable by the rules as published;
it is not a confirmation by the referee's hidden base.
"""
import json
import os
import re

from jsonschema import Draft202012Validator
from referencing import Registry, Resource

from arena.values import WORD_NUMBERS, canonical_amount, comparable, has_negation, parse_values, values_equal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS = os.path.join(ROOT, "contracts")
ID = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")

MONTHS = ["January", "February", "March", "April", "June", "July", "August", "September",
          "October", "November", "December"]
REFUSED_ANY_CASE = MONTHS + [
    "spring", "summer", "autumn", "winter", "Monday", "Tuesday", "Wednesday", "Thursday",
    "Friday", "Saturday", "Sunday", "ago", "yesterday", "tomorrow", "once", "formerly",
    "previously", "originally", "initially", "recently", "lately", "soon", "eventually", "then",
    "before", "after", "since", "until", "till", "earlier", "later", "used to", "last week",
    "last month", "last quarter", "last year", "next week", "next month", "next quarter",
    "next year", "in the past", "in the future", "at the time", "at that time", "now", "today",
    "currently", "still"]
REFUSED = re.compile(r"(?<![\w-])(?:" + "|".join(re.escape(w).replace(r"\ ", r"\s+") for w in REFUSED_ANY_CASE)
                     + r")(?![\w-])", re.I)
REFUSED_MAY = re.compile(r"(?<![\w-])May(?![\w-])")  # `may` is the month only when written May

GAP = r"(?:\s+[\w'’-]+){0,3}\s+"
AMOUNT_PHRASES = {
    "gt": ["more", "higher", "greater", "larger", "bigger", "longer"],
    "lt": ["less", "fewer", "lower", "smaller", "shorter", "cheaper"],
}
PHRASES = []  # (family, op, regex)
for op, words in AMOUNT_PHRASES.items():
    for w in words:
        PHRASES.append(("amount", op, re.compile(rf"\b{w}{GAP}than\b", re.I)))
PHRASES += [("amount", "eq", re.compile(p, re.I)) for p in (
    rf"\bthe\s+same{GAP}as\b", rf"\bas\s+much{GAP}as\b", rf"\bas\s+many{GAP}as\b",
    r"\bas\s+long\s+as\b", r"\bas\s+high\s+as\b", r"\bequal\s+to\b")]
PHRASES += [("date", op, re.compile(p, re.I)) for op, p in (
    ("gt", r"\bafter\b"), ("gt", r"\blater\s+than\b"), ("lt", r"\bbefore\b"),
    ("lt", r"\bearlier\s+than\b"), ("eq", r"\bon\s+the\s+same\s+day\s+as\b"))]
EVENT_PHRASE = re.compile(r"(?:\bat|\bduring|\bon\s+the\s+day\s+of|\bat\s+the\s+time\s+of)\s+(?:the\s+)?$", re.I)
NUMBER_WORDS = set(WORD_NUMBERS) | {"dozen", "hundred", "thousand", "million", "billion"}
SENTENCE_END = re.compile(r"[.!?](?=\s)|\n\s*\n")
# value-forms.md: "The point of an abbreviation ends nothing"
ABBREVIATION = re.compile(r"(?:\b(?:e\.g|i\.e|vs|approx|Inc|Ltd|Co|Corp|Dr|Mr|Mrs|Ms|Prof|St)|(?<![\w.])[A-Z])$")
NO_BEFORE_NUMBER = re.compile(r"\bNo$")


def sentences(text):
    """The sentences of text, as value-forms.md splits them: at `.`, `!` or `?` before a space
    or at a blank line, but not at the point of an abbreviation."""
    out, start = [], 0
    for m in SENTENCE_END.finditer(text):
        before = text[start:m.start()]
        if m.group(0) == "." and (ABBREVIATION.search(before) or
                                  (NO_BEFORE_NUMBER.search(before) and re.match(r"\s*\d", text[m.end():]))):
            continue
        out.append(text[start:m.end()].strip())
        start = m.end()
    out.append(text[start:].strip())
    return [x for x in out if x]


def norm_text(s):
    """As scripts/check_output.py compares texts."""
    return " ".join((s or "").lower().split()).rstrip(".!? ")


def _schema_validator():
    with open(os.path.join(CONTRACTS, "entry.schema.json"), encoding="utf-8") as f:
        entry = json.load(f)
    with open(os.path.join(CONTRACTS, "claimed_value.schema.json"), encoding="utf-8") as f:
        value = json.load(f)
    registry = Registry().with_resource(value["$id"], Resource.from_contents(value))
    return Draft202012Validator(entry, registry=registry)


def attribute_words(attribute):
    """The attribute in words, as the text may write it: `soc2_certified` reads `SOC 2 certified`."""
    return attribute.replace("_", " ")


def _words_regex(attribute):
    """Word for word, any case, a space, a hyphen or nothing between words and between letters and digits."""
    parts = []
    for word in attribute.split("_"):
        pieces = re.findall(r"[a-z]+|[0-9]+", word.lower())
        parts.append(r"[\s-]?".join(re.escape(p) for p in pieces))
    return re.compile(r"(?<![\w])" + r"[\s-]?".join(parts) + r"(?![\w])", re.I)


class Lex:
    """Names of the lexicon, matched as whole words, longest first."""

    def __init__(self, lexicon):
        self.attributes, self.canonical, patterns = {}, {}, []
        for s in lexicon["subjects"]:
            self.attributes[s["name"]] = set(s["attributes"])
            for n in [s["name"]] + list(s.get("aliases", [])):
                self.canonical[n.lower()] = s["name"]
                patterns.append((n, s["name"]))
        self.events = {self.canonical.get(e.lower(), e) for e in lexicon.get("events", [])}
        patterns.sort(key=lambda p: -len(p[0]))
        self.regex = [(re.compile(r"(?<![\w])" + r"\s*".join(re.escape(w) for w in n.split()) + r"(?![\w])", re.I), c)
                      for n, c in patterns]

    def resolve(self, name):
        return self.canonical.get(" ".join(name.split()).lower())

    def find(self, text):
        """Non-overlapping name matches [(start, end, canonical)], the longest name winning."""
        found = []
        for rx, canonical in self.regex:
            for m in rx.finditer(text):
                found.append((m.start(), m.end(), canonical))
        found.sort(key=lambda m: (m[0], -(m[1] - m[0])))
        out, end = [], -1
        for m in found:
            if m[0] >= end:
                out.append(m)
                end = m[1]
        return out


def _mask(text, spans):
    chars = list(text)
    for a, b in spans:
        for i in range(a, b):
            chars[i] = "_" if not chars[i].isspace() else chars[i]
    return "".join(chars)


def _hits(masked):
    """The compare phrases in a sentence, a phrase inside a longer one not counted again:
    `on the same day as` holds `the same day as`."""
    hits = [(fam, op, m) for fam, op, rx in PHRASES for m in rx.finditer(masked)]
    return [h for h in hits if not any(o is not h and o[2].start() <= h[2].start() and h[2].end() <= o[2].end()
                                       and o[2].span() != h[2].span() for o in hits)]


def _phrase_hits(lex, text):
    return _hits(_mask(text, [(a, b) for a, b, _ in lex.find(text)]))


def _rises(frm, to):
    """True when `to` is larger, False when smaller, None when the values have no order."""
    a, b = canonical_amount(frm), canonical_amount(to)
    if not a or not b or a[0] != b[0] or a[1] == b[1]:
        return None
    return b[1] > a[1]


def _strict(parsed):
    return [p for p in parsed if not (p["approx"] or p["range"] or p["negated"]) and "op" not in p["value"]]


def _same(a, b):
    """Exactly the claim's value: equal, and of the same precision for dates."""
    return values_equal(a, b) and (a["kind"] != "date" or a["value"] == b["value"])


class Validator:
    def __init__(self, practice_rows, lexicon, input_texts):
        self.schema = _schema_validator()
        self.lex = Lex(lexicon)
        self.inputs = {norm_text(t) for t in input_texts} | {norm_text(r["text"]) for r in practice_rows}
        self.true_rows, self.kinds = {}, {}
        for r in practice_rows:
            if not r.get("form"):
                continue
            facts = json.loads(r["form"])
            for f in facts:
                self.kinds.setdefault((f["subject"], f["attribute"]), set()).add(f["value"]["kind"])
            if r.get("label") == "true":
                self.true_rows[r["id"]] = {(f["subject"], f["attribute"]) for f in facts}

    # -- 1. schema ------------------------------------------------------------
    def _schema(self, claim, issues):
        entry = {"id": claim.get("id"), "type": claim.get("type"), "text": claim.get("text"),
                 "form": claim.get("form"), "tag": claim.get("label", "true"),
                 "confidence": claim.get("confidence")}
        for e in self.schema.iter_errors(entry):
            issues.append(f"schema: {e.message[:120]}")

    # -- 2. lexicon -----------------------------------------------------------
    def _subject(self, name, attribute, issues, what="subject"):
        canonical = self.lex.resolve(name or "")
        if canonical is None:
            issues.append(f"lexicon: no entity named {name!r}")
        elif attribute not in self.lex.attributes[canonical]:
            issues.append(f"lexicon: {canonical} has no attribute {attribute!r}")
        return canonical

    def _facts(self, t, form, issues):
        """The (subject, attribute) facts the claim rests on, canonical."""
        if t == "compare":
            return [(self._subject(form["left"]["subject"], form["left"]["attribute"], issues),
                     form["left"]["attribute"]),
                    (self._subject(form["right"]["subject"], form["right"]["attribute"], issues),
                     form["right"]["attribute"])]
        if t == "relation":
            s = self._subject(form["subject"], form["link"], issues)
            target = self._subject(form["target"], form["attribute"], issues, "target")
            return [(s, form["link"]), (target, form["attribute"])]
        facts = [(self._subject(form["subject"], form["attribute"], issues), form["attribute"])]
        if t == "at_event":
            event = self.lex.resolve(form["event"])
            if event not in self.lex.events:
                issues.append(f"lexicon: {form['event']!r} is not an event")
            facts.append((event, "date"))  # the event's date is part of the evidence
        return facts

    # -- 3. text --------------------------------------------------------------
    def _text(self, t, form, text, issues):
        """claim-forms.md: one sentence holds the claim; other sentences may say anything, but no
        sentence of a compare holds a second phrase of the list."""
        parts = sentences(text)
        if len(parts) == 1:
            return self._sentence(t, form, parts[0], issues)
        results = []
        for part in parts:
            found = []
            self._sentence(t, form, part, found)
            results.append(found)
        if t == "compare" and sum(len(_phrase_hits(self.lex, part)) for part in parts) > 1:
            issues.append("text: a second compare phrase in another sentence")
        if all(results):
            issues.extend(min(results, key=len))

    def _sentence(self, t, form, text, issues):
        names = self.lex.find(text)
        name_spans = [(a, b) for a, b, _ in names]
        masked = _mask(text, name_spans)
        negated = has_negation(text)
        value = form.get("value")
        boolean = isinstance(value, dict) and value.get("kind") == "boolean"
        if negated and not boolean:
            issues.append("text: a negation")

        def named(subject, after=0):
            canonical = self.lex.resolve(subject)
            return next(((a, b) for a, b, c in names if c == canonical and a >= after), None)

        if t in ("fact", "change", "at_event", "relation") and not named(form["subject"]):
            issues.append(f"text: {form['subject']!r} is not named")

        allowed = []  # spans where time words are part of what the form needs
        if t == "compare":
            self._compare(form, text, masked, names, named, issues, allowed)
        elif t == "change":
            self._change(form, masked, issues)
        else:
            self._one_value(form["value"], text, masked, negated, issues)
            if boolean and not _words_regex(form["attribute"]).search(masked):
                issues.append("text: a yes or no without its attribute's words")
            if t == "at_event":
                span = named(form["event"])
                if not span or not EVENT_PHRASE.search(text[:span[0]]):
                    issues.append("text: no event phrase right before the event")
                elif span:
                    m = EVENT_PHRASE.search(text[:span[0]])
                    allowed.append((m.start(), span[0]))
            if t == "relation" and not _words_regex(form["link"]).search(masked):
                issues.append(f"text: no relation words for {form['link']!r}")
        if t != "change":
            scan = _mask(masked, allowed + self._value_spans(form, masked))
            m = REFUSED.search(scan) or REFUSED_MAY.search(scan)
            if m:
                issues.append(f"text: a date or time word {m.group(0)!r}")

    def _value_spans(self, form, masked):
        v = form.get("value")
        if isinstance(v, dict) and v.get("kind") == "date":
            return [(p["start"], p["end"]) for p in parse_values(masked) if p["value"]["kind"] == "date"]
        return []

    def _one_value(self, value, text, masked, negated, issues):
        parsed = parse_values(masked)
        kind = value["kind"]
        if kind == "boolean":
            if negated == bool(value["value"]):
                issues.append("text: states the other polarity")
            return
        if kind != "date" and any(p["value"]["kind"] == "date" for p in parsed):
            issues.append("text: a date of its own")
        if kind == "name":
            rx = re.compile(r"(?<![\w])" + r"\s*".join(re.escape(w) for w in value["value"].split()) + r"(?![\w])", re.I)
            if not rx.search(text):
                issues.append("text: the name value is not written")
            return
        # "of its kind": a yearly price is another kind than a monthly one; units that convert are one
        same_kind = [p for p in parsed if p["value"]["kind"] == kind and
                     (kind in ("date", "version") or comparable(p["value"], value))]
        exact = [p for p in _strict(same_kind) if _same(p["value"], value)]
        if len(same_kind) != 1 or len(exact) != 1:
            issues.append(f"text: value read as {[p['value'] for p in same_kind]}, not {value}")

    def _change(self, form, masked, issues):
        frm, to = form["from"], form["to"]
        if frm["kind"] == "name":
            low = masked.lower()
            a, b = low.find("from " + frm["value"].lower()), low.find(" to " + to["value"].lower())
            if a < 0 or b < a:
                issues.append("text: no `from … to …` with both names")
            return
        same_kind = [p for p in parse_values(masked) if p["value"]["kind"] == frm["kind"]]
        # `from X to Y` is the change phrase here, not a range
        plain = [p for p in same_kind if not (p["approx"] or p["negated"]) and "op" not in p["value"]]
        if len(same_kind) != 2 or plain != same_kind:
            issues.append(f"text: change values read as {[p['value'] for p in same_kind]}")
            return
        first, second = same_kind
        between = masked[first["end"]:second["start"]]
        since = re.fullmatch(r",\s*(up|down)\s+from\s+", between, re.I)  # `to, up from from`
        if since:
            direction = since.group(1).lower()
            if not (_same(first["value"], to) and _same(second["value"], frm)):
                issues.append("text: the values are not to and from, in that order")
        else:
            lead = re.search(r"\b(?:(up|down)\s+)?from\s+$", masked[:first["start"]], re.I)
            if not lead or not re.fullmatch(r"\s+to\s+", between, re.I):
                issues.append("text: no `from … to …` phrase")
                return
            direction = (lead.group(1) or "").lower()
            if not (_same(first["value"], frm) and _same(second["value"], to)):
                issues.append("text: the values are not from and to, in that order")
        if direction:
            rises = _rises(frm, to)
            if rises is None:
                issues.append(f"text: `{direction}` between values with no order")
            elif rises != (direction == "up"):
                issues.append(f"text: `{direction}` states the other direction")

    def _compare(self, form, text, masked, names, named, issues, allowed):
        hits = _hits(masked)
        if len(hits) != 1:
            issues.append(f"text: {len(hits)} compare phrases, not one")
            return
        fam, op, m = hits[0]
        allowed.append(m.span())
        kinds = self.kinds.get((self.lex.resolve(form["left"]["subject"]), form["left"]["attribute"]), set())
        if fam != ("date" if kinds == {"date"} else "amount"):
            issues.append(f"text: a {fam} phrase between values of kind {sorted(kinds)}")
        if op != form["op"]:
            issues.append(f"text: the phrase states {op}, the form {form['op']}")
        left = named(form["left"]["subject"])
        right = named(form["right"]["subject"], after=m.end())
        if not left or left[1] > m.start() or not right:
            issues.append("text: not `left … phrase … right`")
        if parse_values(masked):
            issues.append("text: a value in a compare")
        if re.search(r"\d", masked) or NUMBER_WORDS & set(re.findall(r"[a-z]+", masked.lower())):
            issues.append("text: a number in a compare")

    # -- 4. evidence ----------------------------------------------------------
    def _evidence(self, facts, ids, issues):
        if not ids:
            issues.append("evidence: none")
            return
        wanted = set(facts)
        for rid in ids:
            stated = self.true_rows.get(rid)
            if stated is None:
                issues.append(f"evidence: {rid} is not a practice row labelled true")
            elif not stated & wanted:
                issues.append(f"evidence: {rid} states none of the claim's facts")

    def text_issues(self, t, form, text):
        """Only the text rules (3), for one form and text."""
        issues = []
        self._text(t, form, text, issues)
        return issues

    def validate(self, claim):
        issues = []
        self._schema(claim, issues)
        if issues:
            return {"valid": False, "issues": issues}
        t, form, text = claim["type"], claim["form"], claim["text"]
        facts = self._facts(t, form, issues)
        if t == "compare" and facts[0] == facts[1]:
            issues.append("compare: a fact with itself")
        if not issues:
            self._text(t, form, text, issues)
        self._evidence(facts, claim.get("evidence_ids") or [], issues)
        if not ID.match(claim["id"]):
            issues.append("id")
        if norm_text(text) in self.inputs:
            issues.append("novelty: the text is an input row")
        return {"valid": not issues, "issues": issues}


_CACHE = {}


def validate_claim(claim, practice_rows, lexicon, input_texts):
    key = (id(practice_rows), id(lexicon), id(input_texts))
    if key not in _CACHE:
        _CACHE.clear()
        _CACHE[key] = Validator(practice_rows, lexicon, input_texts)
    return _CACHE[key].validate(claim)
