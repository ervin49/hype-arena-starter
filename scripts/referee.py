"""An independent referee for the claims of an output.csv, written from the published spec only.

It reads contracts/README.md (the table), contracts/claim-forms.md (what a claim's text must
hold), contracts/value-forms.md (how a value is written), the two schemas in contracts/ and the
dataset's lexicon. It shares no code with arena/: its value reader, names, sentences and claim
forms are a second reading of the spec, so that a claim both readings accept is likelier to
survive the organisers' referee.

For every claim row it prints each rule the claim breaks, with the sentence, then a count per
rule. Exit 1 if any claim is rejected, 0 otherwise. Style notes (a subject not written as the
lexicon writes it) are listed apart and never reject.

    .venv/bin/python scripts/referee.py OUTPUT.csv [--lexicon data/lexicon.json]
                                        [--input universe.csv] [--practice data/practice.csv]

--input: the run's input, to check that no claim text is an input row (claims must be new).
--practice: forms to learn each attribute's kind from, for the compare kind checks.
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONTRACTS = os.path.join(ROOT, "contracts")

# --------------------------------------------------------------------------------------------
# Words of the spec

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december"]
MONTH_ABBR = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8, "sep": 9,
              "sept": 9, "oct": 10, "nov": 11, "dec": 12}
MONTH_NUM = {m: i + 1 for i, m in enumerate(MONTHS)} | MONTH_ABBR
MONTH_RE = r"(?:January|February|March|April|May|June|July|August|September|October|November|December|" \
           r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)\.?"
# claim-forms.md, "Refused"
REFUSED_DATES = MONTHS + ["spring", "summer", "autumn", "winter", "monday", "tuesday", "wednesday",
                          "thursday", "friday", "saturday", "sunday"]
TIME_WORDS = ["ago", "yesterday", "tomorrow", "once", "formerly", "previously", "originally", "initially",
              "recently", "lately", "soon", "eventually", "then", "before", "after", "since", "until",
              "till", "earlier", "later", "used to", "last week", "last month", "last quarter", "last year",
              "next week", "next month", "next quarter", "next year", "in the past", "in the future",
              "at the time", "at that time"]
# value-forms.md, "Yes or no"
NEGATION = r"\b(?:not|no|never|none|nobody|nothing|neither|nor|without|cannot)\b|\b\w+n[’']t\b"
# comparison words that hold a negation word but are part of their value
OP_NEGATIONS = r"\b(?:no more than|not more than|no less than|not less than|no fewer than|no later than|no earlier than)\b"
CLAUSE_END = r"[.,;:!?•·|]|\n\s*\n"

APPROX_BEFORE = r"(?:about|around|approximately|approx\.?|roughly|nearly|almost|circa|ca\.?|some|estimated|est\.?|close to|more or less)"
APPROX_AFTER = r"^(?:\s+or so\b|\s+give or take\b|-ish\b)"

OPS_BEFORE = [  # longest first, so "no more than" is not read as "more than"
    ("le", "no more than"), ("le", "not more than"), ("ge", "no less than"), ("ge", "not less than"),
    ("ge", "no fewer than"), ("le", "no later than"), ("ge", "no earlier than"),
    ("gt", "more than"), ("gt", "greater than"), ("gt", "higher than"), ("gt", "in excess of"),
    ("gt", "upwards of"), ("lt", "less than"), ("lt", "fewer than"), ("lt", "lower than"),
    ("le", "up to"), ("le", "at most"), ("ge", "at least"), ("lt", "prior to"),
    ("gt", "over"), ("gt", "above"), ("gt", "exceeding"), ("lt", "under"), ("lt", "below"),
    ("le", "maximum"), ("le", "max"), ("ge", "minimum"),
]
DATE_OPS_BEFORE = [("lt", "before"), ("gt", "after"), ("le", "by")]
DURATION_OPS_BEFORE = [("le", "within")]
OPS_AFTER = [("le", r"or (?:less|fewer|under|below|lower|shorter)"), ("ge", r"or (?:more|higher|above|longer|over)")]

WORD_NUMBERS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
    "sixteen seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90}
UNITS_1_9 = "one|two|three|four|five|six|seven|eight|nine"
WORD_NUMBER_RE = (r"\b(?:a hundred|(?:" + UNITS_1_9 + r") hundred|a dozen|(?:" + "|".join(TENS) + r")(?:-(?:" + UNITS_1_9 +
                  r"))?|" + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + r")\b")

# value-forms.md, "Quantity": symbol or spelling -> (dimension, factor to the base unit)
PHYSICAL = {}
for sym, f in (("B", 1), ("KB", 1e3), ("MB", 1e6), ("GB", 1e9), ("TB", 1e12)):
    PHYSICAL[sym] = ("data", f)
for alias, sym in (("kB", "KB"), ("kb", "KB"), ("mb", "MB"), ("gb", "GB"), ("tb", "TB")):
    PHYSICAL[alias] = PHYSICAL[sym]
for sym, f in (("mm", 1e-3), ("cm", 1e-2), ("m", 1), ("km", 1e3), ("in", 0.0254)):
    PHYSICAL[sym] = ("length", f)
for sym, f in (("g", 1), ("kg", 1e3)):
    PHYSICAL[sym] = ("mass", f)
PHYSICAL["mAh"] = ("charge", 1)
for sym, f in (("Hz", 1), ("kHz", 1e3), ("MHz", 1e6), ("GHz", 1e9)):
    PHYSICAL[sym] = ("frequency", f)
for sym, f in (("mW", 1e-3), ("W", 1), ("kW", 1e3)):
    PHYSICAL[sym] = ("power", f)
UNIT_WORDS = {  # spellings that read in any case, singular or plural
    "byte": "B", "kilobyte": "KB", "megabyte": "MB", "gigabyte": "GB", "gig": "GB", "terabyte": "TB",
    "millimetre": "mm", "millimeter": "mm", "centimetre": "cm", "centimeter": "cm", "metre": "m", "meter": "m",
    "kilometre": "km", "kilometer": "km", "inch": "in", "gram": "g", "gramme": "g", "kilogram": "kg", "kilo": "kg",
    "hertz": "Hz", "kilohertz": "kHz", "megahertz": "MHz", "gigahertz": "GHz",
    "milliwatt": "mW", "watt": "W", "kilowatt": "kW",
}
# value-forms.md, "Duration": spelling -> (unit, multiplier). Months and years do not convert to days.
DURATION_WORDS = {
    "ms": ("ms", 1), "millisecond": ("ms", 1), "s": ("s", 1), "sec": ("s", 1), "second": ("s", 1),
    "min": ("min", 1), "minute": ("min", 1), "h": ("h", 1), "hr": ("h", 1), "hour": ("h", 1),
    "day": ("day", 1), "d": ("day", 1), "week": ("week", 1), "wk": ("week", 1), "fortnight": ("week", 2),
    "month": ("month", 1), "mo": ("month", 1), "mth": ("month", 1), "year": ("year", 1), "yr": ("year", 1),
    "decade": ("year", 10),
}
DURATION_SECONDS = {"ms": 1e-3, "s": 1, "min": 60, "h": 3600, "day": 86400, "week": 604800}
DURATION_MONTHS = {"month": 1, "year": 12}
A_IS_ONE_AFTER = r"(?:under|within|in|for|over|than|at least|at most|to|only|just|about|around)"

CURRENCY_SYMBOL = {"US$": "USD", "€": "EUR", "$": "USD", "£": "GBP"}
ISO_CODES = "EUR USD GBP CHF RON PLN CZK HUF SEK NOK DKK JPY CNY INR CAD AUD".split()
CURRENCY_WORDS = {"euro": "EUR", "euros": "EUR", "dollar": "USD", "dollars": "USD", "lei": "RON"}
PERIOD_RE = (r"^\s*(?:(?:per user|per seat|/user|/seat)\s*)?"
             r"(?:/\s?(?P<slash>month|mo|day|week|wk|year|yr)\b|(?:a|per)\s+(?P<word>month|day|week|year)\b|"
             r"(?P<adv>monthly|daily|weekly|yearly|annually)\b|(?P<annum>per annum)\b)")
PERIOD_NORM = {"mo": "month", "wk": "week", "yr": "year", "monthly": "month", "daily": "day", "weekly": "week",
               "yearly": "year", "annually": "year"}

# claim-forms.md, the compare phrases: (family, op, phrase); "…" is up to three words
COMPARE_PHRASES = [
    ("amount", "gt", p) for p in ("more … than", "higher … than", "greater … than", "larger … than",
                                  "bigger … than", "longer … than")
] + [
    ("amount", "lt", p) for p in ("less … than", "fewer … than", "lower … than", "smaller … than",
                                  "shorter … than", "cheaper … than")
] + [
    ("amount", "eq", p) for p in ("the same … as", "as much … as", "as many … as", "as long as", "as high as",
                                  "equal to")
] + [("date", "gt", "after"), ("date", "gt", "later than"), ("date", "lt", "before"), ("date", "lt", "earlier than"),
     ("date", "eq", "on the same day as"), ("date", "eq", "the same day as")]
EVENT_PHRASES = ["on the day of", "at the time of", "during", "at"]
AMOUNT_KINDS = {"quantity", "money", "percent", "duration", "version"}
ABBREVIATIONS = ["e.g.", "i.e.", "vs.", "approx.", "Inc.", "Ltd.", "Co.", "Corp.", "Dr.", "Mr.", "Mrs.", "Ms.",
                 "Prof.", "St.", "ver.", "ca.", "est."] + [m.capitalize() + "." for m in MONTH_ABBR]


def phrase_re(phrase):
    words = [re.escape(w) for w in phrase.split()]
    out = []
    for w in words:
        out.append(r"(?:\s+[\w’'-]+){0,3}" if w == "…" else (r"\s+" if out else "") + w)
    return re.compile(r"\b" + "".join(out) + r"\b", re.I)


COMPARE_RES = [(fam, op, ph, phrase_re(ph)) for fam, op, ph in COMPARE_PHRASES]


def words_re(attribute):
    """An attribute in words: its words with a space, a hyphen or nothing between them, and between
    a word's letters and digits (soc2_certified reads SOC 2 certified, SOC2-certified)."""
    parts = []
    for w in attribute.split("_"):
        parts += re.findall(r"[a-z]+|\d+", w)
    return re.compile(r"(?<![\w])" + r"[\s-]*".join(re.escape(p) for p in parts) + r"(?![\w])", re.I)


def singular(word):
    w = word.lower().strip("’'")
    irregular = {"people": "person", "children": "child", "men": "man", "women": "woman", "data": "data"}
    if w in irregular:
        return irregular[w]
    if w.endswith("ies") and len(w) > 4:
        return w[:-3] + "y"
    if re.search(r"(sses|xes|ches|shes|zes)$", w):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss") and len(w) > 2:
        return w[:-1]
    return w


# --------------------------------------------------------------------------------------------
# Names (lexicon.json)

class Lexicon:
    def __init__(self, data):
        self.entities = {}        # canonical name -> set of attributes
        self.spellings = []       # (spelling, canonical)
        self.events = set()
        for s in data.get("subjects", []):
            self.entities[s["name"]] = set(s.get("attributes") or [])
            for sp in [s["name"]] + list(s.get("aliases") or []):
                self.spellings.append((sp, s["name"]))
        for e in data.get("events", []):
            name = e if isinstance(e, str) else e.get("name")
            self.events.add(name)
            if name not in self.entities:
                self.entities[name] = {"date"}
                self.spellings.append((name, name))
        self.spellings.sort(key=lambda x: -len(x[0]))
        self._res = [(re.compile(r"(?<![\w])" + r"\s*".join(re.escape(p) for p in sp.split()) + r"(?![\w])", re.I), c)
                     for sp, c in self.spellings]
        self._key = {self.key(sp): c for sp, c in self.spellings}

    @staticmethod
    def key(s):
        return re.sub(r"\s+", "", s).lower()

    def resolve(self, name):
        """The canonical name a form's name stands for, or None."""
        return self._key.get(self.key(name or ""))

    def find(self, text):
        """[(start, end, canonical)] of every name, a name inside a longer one naming that one only."""
        hits = []
        for rx, c in self._res:
            for m in rx.finditer(text):
                hits.append((m.start(), m.end(), c))
        hits.sort(key=lambda h: (-(h[1] - h[0]), h[0]))
        kept = []
        for h in hits:
            if all(h[1] <= k[0] or h[0] >= k[1] for k in kept):
                kept.append(h)
        return sorted(kept)

    def name_hits(self, text, name):
        """[(start, end)] where text names a name value: its own words, or a lexicon spelling of the
        entity it resolves to; whole words, any case and spacing. A hit inside another entity's
        longer name names that one only."""
        c = self.resolve(name)
        spellings = [sp for sp, cc in self.spellings if cc == c] if c else [name]
        longer = [(a, b) for a, b, cc in self.find(text) if cc != c]
        out = []
        for sp in spellings:
            rx = r"(?<![\w])" + r"\s*".join(re.escape(p) for p in sp.split()) + r"(?![\w])"
            for m in re.finditer(rx, text, re.I):
                if not any(a <= m.start() and m.end() <= b and (b - a) > (m.end() - m.start()) for a, b in longer):
                    out.append((m.start(), m.end()))
        return sorted(set(out))

    def same_type(self, a, b):
        """Two entities of one type: they share an attribute (a person with a person)."""
        return bool(self.entities.get(a, set()) & self.entities.get(b, set()))


# --------------------------------------------------------------------------------------------
# Sentences

def sentences(text):
    """[(start, end)] of the text's sentences: they end at . ! ? before a space, or at a blank line;
    the point of an abbreviation, an initial or "No." before a number ends nothing."""
    out, start, i = [], 0, 0
    while i < len(text):
        ch = text[i]
        if text.startswith("\n", i) and re.match(r"\n[ \t]*\n", text[i:]):
            m = re.match(r"\n[ \t]*\n\s*", text[i:])
            out.append((start, i))
            i += m.end()
            start = i
            continue
        if ch in ".!?" and (i + 1 == len(text) or text[i + 1].isspace()):
            before = text[start:i + 1]
            if ch == "." and (any(before.endswith(" " + a) or before == a for a in ABBREVIATIONS)
                              or re.search(r"(?:^|\s)[A-Z]\.$", before)
                              or (re.search(r"(?:^|\s)No\.$", before) and re.match(r"\s+\d", text[i + 1:]))):
                i += 1
                continue
            out.append((start, i + 1))
            i += 1
            while i < len(text) and text[i].isspace():
                i += 1
            start = i
            continue
        i += 1
    if text[start:].strip():
        out.append((start, len(text)))
    return [(s, e) for s, e in out if text[s:e].strip()]


# --------------------------------------------------------------------------------------------
# The value reader (value-forms.md)

def _blank(s, a, b):
    return s[:a] + " " * (b - a) + s[b:]


def _number(tok, money=False, percent=False):
    """The number a token writes, or None when it could mean two things."""
    if re.fullmatch(r"\d{1,3}(?:,\d{3})+(?:\.\d+)?", tok):
        return float(tok.replace(",", ""))
    if re.fullmatch(r"\d+", tok):
        return float(tok)
    if re.fullmatch(r"\d+\.\d+", tok):
        if len(tok.split(".")[1]) == 3 and not percent:
            return None                      # 1.500: one and a half, or fifteen hundred
        return float(tok)
    if money and re.fullmatch(r"\d+,\d{1,2}", tok):
        return float(tok.replace(",", "."))  # a decimal comma reads in a price only
    return None


def _word_number(w):
    w = w.lower()
    if w == "a hundred":
        return 100
    if w == "a dozen":
        return 12
    m = re.fullmatch(r"(\w+) hundred", w)
    if m:
        return WORD_NUMBERS[m.group(1)] * 100
    if w in WORD_NUMBERS:
        return WORD_NUMBERS[w]
    m = re.fullmatch(r"(\w+)(?:-(\w+))?", w)
    if m and m.group(1) in TENS:
        return TENS[m.group(1)] + (WORD_NUMBERS[m.group(2)] if m.group(2) else 0)
    return None


def _clean(x):
    return int(x) if abs(x - round(x)) < 1e-9 else round(x, 6)


class Reader:
    """Every value a sentence writes: [{value, start, end, op, approx, range, negated}]; also the
    numbers it holds, read as values or not."""

    def __init__(self, text, masks=()):
        self.text = text
        work = text
        for a, b in masks:
            work = _blank(work, a, b)
        self.work = work
        self.values, self.numbers = [], []
        self._read()

    # -- one pass per kind, each masking what it reads -------------------------------------------
    def _add(self, value, a, b):
        self.values.append({"value": value, "start": a, "end": b})
        self.work = _blank(self.work, a, b)

    def _read(self):
        w = self.work
        # numbers anywhere, for compare's "no number at all"
        self.numbers = [(m.start(), m.end()) for m in re.finditer(r"\d", w)]
        self.numbers += [(m.start(), m.end()) for m in re.finditer(WORD_NUMBER_RE + r"|\b(?:hundred|dozen|thousand|million|billion)\b", w, re.I)]
        self._dates()
        self._versions()
        self._money()
        self._percents()
        self._durations()
        self._quantities()
        self.values.sort(key=lambda v: v["start"])
        for v in self.values:
            self._flags(v)

    def _dates(self):
        w = self.work
        day = r"(?P<d>\d{1,2})(?:st|nd|rd|th)?"
        pats = [
            r"(?<![\w./-])(?P<y>\d{4})-(?P<m>\d{2})(?:-(?P<d>\d{2}))?(?![\w-])",
            r"(?<![\w./])(?:the\s+)?" + day + r"(?:\s+of)?\s*(?P<mn>" + MONTH_RE + r")\s+(?P<y>\d{4})(?![\w.,]\d)",
            r"(?<![\w.])(?P<mn>" + MONTH_RE + r")\s+" + day + r",?\s+(?P<y>\d{4})(?![\w.,]\d)",
            r"(?<![\w.])(?P<mn>" + MONTH_RE + r")\s+(?P<y>\d{4})(?![\w.,]\d)",
        ]
        for p in pats:
            for m in list(re.finditer(p, self.work, re.I)):
                if m.group(0).strip() == "":
                    continue
                gd = m.groupdict()
                if gd.get("mn") and gd["mn"].rstrip(".") == "may":
                    continue                                  # "may" is the month only as May
                y = int(gd["y"])
                mo = int(gd["m"]) if gd.get("m") else MONTH_NUM.get(gd["mn"].rstrip(".").lower()) if gd.get("mn") else None
                d = int(gd["d"]) if gd.get("d") else None
                iso = _iso(y, mo, d)
                if iso:
                    self._add({"kind": "date", "value": iso}, m.start(), m.end())
        # numeric dates do not read, but they are dates all the same (12/03/2026, 12.03.2026)
        for m in list(re.finditer(r"(?<![\w.])\d{1,2}[./]\d{1,2}[./]\d{2,4}(?![\w.])", self.work)):
            self._add({"kind": "date", "value": None}, m.start(), m.end())
        # a plain four-digit number from 1900 to 2099 is a year; quarters and halves are no dates
        for m in list(re.finditer(r"(?<![\w.,/$€£-])(19\d\d|20\d\d)(?![\w.,]\d|\d|-\d)", self.work)):
            if re.search(r"\b[QH][1-4]\s*$", self.work[:m.start()]):
                self.work = _blank(self.work, m.start(), m.end())
                continue
            if re.match(r"\s*(?:%|percent|per cent)", self.work[m.end():]):
                continue
            self._add({"kind": "date", "value": m.group(1)}, m.start(), m.end())

    def _versions(self):
        for m in list(re.finditer(r"\b(?:version|ver\.|v)\s?(\d+(?:\.\d+){0,3})(?![\d.]*\d)", self.work, re.I)):
            self._add({"kind": "version", "value": m.group(1)}, m.start(), m.end())
        for m in list(re.finditer(r"(?<![\w.,])(\d+(?:\.\d+){2,3})(?![\w.]*\d)", self.work)):
            self._add({"kind": "version", "value": m.group(1)}, m.start(), m.end())
        # one decimal point straight after a capitalised name: Hooly Gemini 2.2
        for m in list(re.finditer(r"\b[A-Z][\w’']*\s(\d+\.\d+)(?![\w.]*\d)", self.text)):
            a, b = m.start(1), m.end(1)
            if self.work[a:b] != m.group(1) or re.match(r"\s?(?:%|percent|per cent)", self.work[b:]):
                continue
            self._add({"kind": "version", "value": m.group(1)}, a, b)

    def _num_at(self, a, money=False, percent=False):
        """(value, end) of a number starting at a: digits with a scale, or words; or None."""
        w = self.work
        m = re.match(r"\d[\d.,]*\d|\d", w[a:])
        if m:
            tok = m.group(0)
            x = _number(tok, money=money, percent=percent)
            if x is None:
                return None
            e = a + m.end()
            sc = re.match(r"(?:\s?(?P<w>thousand|million|billion)\b|(?P<s>M|bn|k)\b)", w[e:])
            if sc:
                x *= {"thousand": 1e3, "million": 1e6, "billion": 1e9, "M": 1e6, "bn": 1e9, "k": 1e3}[sc.group("w") or sc.group("s")]
                e += sc.end()
            return x, e
        m = re.match(WORD_NUMBER_RE, w[a:], re.I)
        if m:
            return _word_number(m.group(0)), a + m.end()
        return None

    def _starts(self):
        """Where numbers start, in reading order."""
        w = self.work
        out = [m.start() for m in re.finditer(r"(?<![\w.,])\d", w)]
        out += [m.start() for m in re.finditer(WORD_NUMBER_RE, w, re.I)]
        return sorted(set(out))

    def _money(self):
        w = self.work
        sym = r"(?P<sym>US\$|€|\$|£)\s?|(?P<code>" + "|".join(ISO_CODES) + r")\s"
        for m in list(re.finditer(r"(?:" + sym + r")(?=\d)", self.work)):
            got = self._num_at(m.end(), money=True)
            if not got:
                continue
            x, e = got
            cur = CURRENCY_SYMBOL.get(m.group("sym")) if m.group("sym") else m.group("code")
            self._money_value(x, cur, m.start(), e)
        for a in self._starts():
            if self.work[a] == " ":
                continue
            got = self._num_at(a, money=True)
            if not got:
                continue
            x, e = got
            mc = re.match(r"\s?(?P<code>" + "|".join(ISO_CODES) + r")\b|\s+(?P<word>euros?|dollars?|lei)\b", self.work[e:], re.I)
            if mc and (mc.group("code") is None or mc.group("code").isupper()):
                cur = mc.group("code") or CURRENCY_WORDS[mc.group("word").lower()]
                self._money_value(x, cur, a, e + mc.end())

    def _money_value(self, x, cur, a, e):
        v = {"kind": "money", "value": _clean(x), "currency": cur}
        pm = re.match(PERIOD_RE, self.work[e:], re.I)
        if pm:
            per = pm.group("slash") or pm.group("word") or pm.group("adv") or ("year" if pm.group("annum") else None)
            v["per"] = PERIOD_NORM.get(per.lower(), per.lower())
            e += pm.end()
        self._add(v, a, e)

    def _percents(self):
        for a in self._starts():
            if self.work[a] == " ":
                continue
            got = self._num_at(a, percent=True)
            if not got:
                continue
            x, e = got
            pm = re.match(r"\s?%|\s+(?:percent|per cent)\b", self.work[e:], re.I)
            if pm:
                self._add({"kind": "percent", "value": _clean(x)}, a, e + pm.end())

    def _durations(self):
        units = sorted(DURATION_WORDS, key=len, reverse=True)
        unit_re = r"(?P<u>" + "|".join(units) + r")(?P<pl>s)?\b"
        for a in self._starts():
            if self.work[a] == " ":
                continue
            got = self._num_at(a)
            if not got:
                continue
            x, e = got
            um = re.match(r"(?:-|\s?)" + unit_re, self.work[e:], re.I)
            if not um:
                continue
            u = um.group("u")
            if len(u) == 1 and (u != u.lower() or um.group("pl")):
                continue                           # a single-letter unit is lower case
            if u.lower() in ("ms", "mo", "mth") and um.group("pl"):
                continue
            unit, mult = DURATION_WORDS[u.lower()]
            self._add({"kind": "duration", "value": _clean(x * mult), "unit": unit}, a, e + um.end())
        # "a" or "an" counts as one after under, within, in, for ...
        for m in list(re.finditer(r"\b" + A_IS_ONE_AFTER + r"\s+(?P<a>an?)\s+" + unit_re, self.work, re.I)):
            u = m.group("u")
            if len(u) == 1:
                continue
            unit, mult = DURATION_WORDS[u.lower()]
            self._add({"kind": "duration", "value": mult, "unit": unit}, m.start("a"), m.end())

    def _quantities(self):
        for a in self._starts():
            if self.work[a] == " ":
                continue
            got = self._num_at(a)
            if not got:
                continue
            x, e = got
            rest = self.work[e:]
            if rest[:1] in ('"', "″"):
                self._add({"kind": "quantity", "value": _clean(x), "unit": "in"}, a, e + 1)
                continue
            sm = re.match(r"(?:\s?|-)(?P<u>[A-Za-z]+)\b", rest)
            if sm and sm.group("u") in PHYSICAL:
                self._add({"kind": "quantity", "value": _clean(x), "unit": sm.group("u")}, a, e + sm.end())
                continue
            if sm and singular(sm.group("u")) in UNIT_WORDS:
                self._add({"kind": "quantity", "value": _clean(x), "unit": UNIT_WORDS[singular(sm.group("u"))]}, a, e + sm.end())
                continue
            # a counted noun: up to two words may come between the number and its noun
            wm = re.match(r"\+?(?:\s+(?P<w1>[A-Za-z][\w’'-]*))(?:\s+(?P<w2>[A-Za-z][\w’'-]*))?(?:\s+(?P<w3>[A-Za-z][\w’'-]*))?", rest)
            if not wm or not wm.group("w1"):
                continue
            words = [(wm.group(k), wm.end(k)) for k in ("w1", "w2", "w3") if wm.group(k)]
            self._add({"kind": "quantity", "value": _clean(x), "unit": singular(words[0][0]),
                       "nouns": [(singular(wd), e + end) for wd, end in words]}, a, e + words[0][1])

    def _flags(self, v):
        t, a, b = self.text, v["start"], v["end"]
        before = t[:a]
        kind = v["value"]["kind"]
        v["op"] = None
        ops = OPS_BEFORE + (DATE_OPS_BEFORE if kind == "date" else []) + (DURATION_OPS_BEFORE if kind == "duration" else [])
        for op, words in sorted(ops, key=lambda o: -len(o[1])):
            if re.search(r"\b" + re.escape(words) + r"\s*$", before, re.I):
                v["op"] = op
                break
        after = t[b:]
        for op, words in OPS_AFTER:
            if re.match(r"\s+" + words + r"\b", after, re.I):
                v["op"] = op
        if re.match(r"\+", after) or re.match(r"[^\d]*\d[\d.,]*\+", t[a:b]):
            v["op"] = "ge"
        v["approx"] = bool(re.search(r"(?:\b" + APPROX_BEFORE + r"\s*|[~≈±]\s*)$", before, re.I)
                           or re.match(APPROX_AFTER, after, re.I))
        v["range"] = bool(
            re.search(r"\d[\d.,]*\s*(?:[A-Za-z%]+\s*)?(?:-|–|—|\bto\b)\s*$", before)
            or re.match(r"\s*(?:-|–|—)\s*[€$£]?\d", after)
            or re.match(r"\s+to\s+(?:[€$£]|US\$)?\d", after)
            or re.search(r"\bbetween\s+[€$£]?\d[\d.,]*\s*(?:[A-Za-z%]+\s*)?and\s*$", before, re.I)
            or re.search(r"\bbetween\s*$", before, re.I)
            or re.search(r"(?<![\w.,])\d[\d.,]*\s+or\s*$", before)
        )
        v["negated"] = negated_before(t, a)


def _iso(y, mo=None, d=None):
    import calendar
    if not 1000 <= y <= 9999:
        return None
    if mo is None:
        return f"{y:04d}"
    if not 1 <= mo <= 12:
        return None
    if d is None:
        return f"{y:04d}-{mo:02d}"
    if not 1 <= d <= calendar.monthrange(y, mo)[1]:
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def _strip_op_negations(s):
    return re.sub(OP_NEGATIONS, lambda m: " " * len(m.group(0)), s, flags=re.I)


def negated_before(text, pos):
    """A negation before pos in its clause."""
    clause = re.split(CLAUSE_END, text[:pos])[-1]
    return bool(re.search(NEGATION, _strip_op_negations(clause), re.I))


def has_negation(text):
    return bool(re.search(NEGATION, _strip_op_negations(text), re.I))


# --------------------------------------------------------------------------------------------
# Values

def physical_unit(u):
    """The symbol of a unit of the Quantity table, from any of its spellings, or None (a counted noun).
    A claim's value may use any spelling listed: GB, gb and gigabyte are one unit."""
    if u in PHYSICAL:
        return u
    return UNIT_WORDS.get(singular(u))


def _amount(v):
    """(dimension, magnitude) to compare amounts in converting units."""
    k = v["kind"]
    if k == "quantity":
        u = physical_unit(v["unit"]) or v["unit"]
        if u in PHYSICAL:
            dim, f = PHYSICAL[u]
            return dim, v["value"] * f
        return "noun:" + singular(u), v["value"]
    if k == "duration":
        if v["unit"] in DURATION_SECONDS:
            return "time", v["value"] * DURATION_SECONDS[v["unit"]]
        return "months", v["value"] * DURATION_MONTHS[v["unit"]]
    if k == "money":
        return f"money:{v['currency']}:{v.get('per')}", v["value"]
    if k == "percent":
        return "percent", v["value"]
    return None


def _close(a, b):
    return abs(a - b) <= max(1e-9, 1e-12 * max(abs(a), abs(b)))


def same_value(read, claim):
    """Whether a value read from a text states the claim's value exactly."""
    if read["kind"] != claim["kind"]:
        return False
    k = claim["kind"]
    if k == "quantity" and not physical_unit(claim["unit"]) and read.get("nouns"):
        return any(n == singular(claim["unit"]) for n, _ in read["nouns"]) and _close(read["value"], claim["value"])
    if k in ("quantity", "duration", "money", "percent"):
        a, b = _amount(read), _amount(claim)
        return bool(a and b and a[0] == b[0] and _close(a[1], b[1]))
    if k in ("date", "version"):
        return read["value"] is not None and str(read["value"]) == str(claim["value"])
    return read == claim


def same_family(read, claim):
    """Whether a value read is "of the claim's kind" for the one-value rule."""
    if read["kind"] != claim["kind"]:
        return False
    k = claim["kind"]
    if k == "quantity":
        cu, ru = physical_unit(claim["unit"]), physical_unit(read["unit"])
        if cu:
            return bool(ru) and PHYSICAL[ru][0] == PHYSICAL[cu][0]
        return any(n == singular(claim["unit"]) for n, _ in read.get("nouns") or [(read["unit"], 0)])
    if k == "duration":
        return _amount(read)[0] == _amount(claim)[0]
    if k == "money":
        return read["currency"] == claim["currency"] and read.get("per") == claim.get("per")
    return True


def bigger(a, b):
    """Whether amount a is larger than amount b; None if they do not compare."""
    if a["kind"] in ("name", "boolean") or a["kind"] != b["kind"]:
        return None
    if a["kind"] == "date":
        return None
    if a["kind"] == "version":
        pa, pb = [int(x) for x in a["value"].split(".")], [int(x) for x in b["value"].split(".")]
        return pa > pb
    x, y = _amount(a), _amount(b)
    if not x or not y or x[0] != y[0]:
        return None
    return x[1] > y[1]


# --------------------------------------------------------------------------------------------
# The claim forms (claim-forms.md)

class Referee:
    def __init__(self, lexicon, kinds=None):
        self.lex = lexicon
        self.kinds = kinds or {}           # attribute -> set of kinds (for compare)

    # -- helpers ----------------------------------------------------------------------------------
    def names_in(self, s):
        return self.lex.find(s)

    def named(self, names, canonical):
        return [n for n in names if n[2] == canonical]

    def plain_values(self, reader):
        return [v for v in reader.values if not v["approx"] and not v["range"]]

    def states(self, reader, value, boolean_ok=False):
        for v in reader.values:
            if v["approx"] or v["range"] or v["op"] not in (None, "eq"):
                continue
            if v["negated"] and not boolean_ok:
                continue
            if same_value(v["value"], value):
                return v
        return None

    def refused_words(self, s, allowed_spans, dates):
        """Months, seasons, days and time words outside the allowed spans and the read dates."""
        out = []
        work = s
        for a, b in list(allowed_spans) + [(d["start"], d["end"]) for d in dates]:
            work = _blank(work, a, b)
        for w in REFUSED_DATES:
            for m in re.finditer(r"\b" + w + r"\b", work, re.I):
                if w == "may" and m.group(0) != "May" and m.group(0) != "MAY":
                    continue
                out.append(m.group(0))
        for w in TIME_WORDS:
            for m in re.finditer(r"\b" + w.replace(" ", r"\s+") + r"\b", work, re.I):
                out.append(m.group(0))
        return out

    def yes_no(self, s, attribute, value):
        """Rules broken by a yes or no in sentence s."""
        errs = []
        if not words_re(attribute).search(s):
            errs.append(("yes_no.attribute_words", f"no '{attribute.replace('_', ' ')}' in words"))
        elif has_negation(s) != (value is False):
            errs.append(("yes_no.polarity", f"the sentence states {'no' if has_negation(s) else 'yes'}"))
        return errs

    def one_value_rules(self, s, names, needed, value, extra_allowed=()):
        """fact, at_event, relation: the value stated, no other value of its kind, no date of its own,
        no refused word, no negation (but for a yes or no)."""
        errs = []
        masks = [(a, b) for a, b, c in names if c in needed]
        r = Reader(s, masks)
        kind = value["kind"]
        if kind == "boolean":
            pass
        elif kind == "name":
            target = self.lex.resolve(value["value"]) or value["value"]
            hits = [h for h in self.lex.name_hits(s, value["value"]) if not negated_before(s, h[0])]
            if not hits:
                errs.append(("value.not_stated", f"no {value['value']!r} in the sentence"))
            others = [n for n in names if n[2] not in needed and n[2] != target and self.lex.same_type(n[2], target)]
            if others:
                errs.append(("value.second_value", "another name of the same type: " + ", ".join(sorted({o[2] for o in others}))))
        else:
            got = self.states(r, value)
            if not got:
                near = [v for v in r.values if same_family(v["value"], value)]
                why = ("written " + ", ".join(repr(s[v["start"]:v["end"]]) + _why(v) for v in near)) if near else "not written"
                errs.append(("value.not_stated", f"{_show(value)}: {why}"))
            others = [v for v in r.values if v is not got and same_family(v["value"], value)]
            if others:
                errs.append(("value.second_value", ", ".join(repr(s[v["start"]:v["end"]]) for v in others)))
        if kind != "date":
            dates = [v for v in r.values if v["value"]["kind"] == "date"]
            if dates:
                errs.append(("date_of_its_own", ", ".join(repr(s[d["start"]:d["end"]]) for d in dates)))
        allowed = masks + list(extra_allowed)
        if kind not in ("boolean",):
            got = self.states(r, value) if kind != "name" else None
            if got:
                allowed.append((got["start"], got["end"]))
        refused = self.refused_words(s, allowed, [v for v in r.values if v["value"]["kind"] == "date"])
        if refused:
            errs.append(("refused_word", ", ".join(sorted(set(refused)))))
        if kind == "boolean":
            errs += self.yes_no(s, self._attr, value["value"])
        elif has_negation(s):
            errs.append(("negation", re.search(NEGATION, _strip_op_negations(s), re.I).group(0)))
        return errs

    # -- the types -------------------------------------------------------------------------------
    def check_sentence(self, typ, form, s):
        names = self.names_in(s)
        fn = getattr(self, "_" + typ)
        return fn(form, s, names)

    def _fact(self, f, s, names):
        subj = self.lex.resolve(f["subject"])
        if not self.named(names, subj):
            return [("subject.not_named", f"{f['subject']} is not named")]
        self._attr = f["attribute"]
        return self.one_value_rules(s, names, {subj}, f["value"])

    def _at_event(self, f, s, names):
        subj, ev = self.lex.resolve(f["subject"]), self.lex.resolve(f["event"])
        errs = []
        if not self.named(names, subj):
            errs.append(("subject.not_named", f"{f['subject']} is not named"))
        phrase_spans = []
        for a, b, c in self.named(names, ev):
            m = re.search(r"\b(?:" + "|".join(re.escape(p) for p in EVENT_PHRASES) + r")\s+(?:the\s+)?$", s[:a], re.I)
            if m:
                phrase_spans.append((m.start(), a))
        if not self.named(names, ev):
            errs.append(("event.not_named", f"{f['event']} is not named"))
        elif not phrase_spans:
            errs.append(("event.phrase", "no event phrase (at, during, on the day of, at the time of) right before the event"))
        if errs and errs[0][0] == "subject.not_named":
            return errs
        self._attr = f["attribute"]
        return errs + self.one_value_rules(s, names, {subj, ev}, f["value"], phrase_spans)

    def _relation(self, f, s, names):
        subj = self.lex.resolve(f["subject"])
        if not self.named(names, subj):
            return [("subject.not_named", f"{f['subject']} is not named")]
        errs = []
        rm = words_re(f["link"]).search(s)
        if not rm:
            errs.append(("relation.words", f"no '{f['link'].replace('_', ' ')}' in words"))
        self._attr = f["attribute"]
        spans = [(rm.start(), rm.end())] if rm else []
        return errs + self.one_value_rules(s, names, {subj}, f["value"], spans)

    def _compare(self, f, s, names, whole_text=None):
        left, right = self.lex.resolve(f["left"]["subject"]), self.lex.resolve(f["right"]["subject"])
        errs = []
        lk = self.kinds.get(f["left"]["attribute"], set())
        rk = self.kinds.get(f["right"]["attribute"], set())
        if (f["left"]["subject"], f["left"]["attribute"]) == (f["right"]["subject"], f["right"]["attribute"]) or left == right and f["left"]["attribute"] == f["right"]["attribute"]:
            errs.append(("compare.same_fact", "a fact compared with itself"))
        family = None
        if lk and rk:
            if lk & {"name", "boolean"} or rk & {"name", "boolean"}:
                errs.append(("compare.kinds", "names and yes-or-no values do not compare"))
            elif lk == {"date"} and rk == {"date"}:
                family = "date"
            elif lk <= AMOUNT_KINDS and rk <= AMOUNT_KINDS and lk & rk:
                family = "amount"
            else:
                errs.append(("compare.kinds", f"{sorted(lk)} against {sorted(rk)}"))
        found = _phrases(s)
        if not found:
            return errs + [("compare.phrase", "no compare phrase")]
        if len(found) > 1:
            errs.append(("compare.second_phrase", ", ".join(repr(p[3]) for p in found)))
        ph = found[0]
        fam, op = ph[0], ph[1]
        if family and fam != family:
            errs.append(("compare.phrase_kind", f"{ph[3]!r} is a {fam} phrase between {family}s"))
        if op != f["op"]:
            errs.append(("compare.op", f"{ph[3]!r} states {op}, the form {f['op']}"))
        lefts = [n for n in self.named(names, left) if n[1] <= ph[4]]
        rights = [n for n in self.named(names, right) if n[0] >= ph[5]]
        if not lefts:
            errs.append(("compare.left", f"{f['left']['subject']} is not named before the phrase"))
        if not rights:
            errs.append(("compare.right", f"{f['right']['subject']} is not named after the phrase"))
        masks = [(a, b) for a, b, c in names if c in (left, right)]
        r = Reader(s, masks)
        if r.values:
            errs.append(("compare.value", ", ".join(repr(s[v["start"]:v["end"]]) for v in r.values)))
        else:
            work = s
            for a, b in masks:
                work = _blank(work, a, b)
            nums = re.findall(r"\d+|" + WORD_NUMBER_RE + r"|\b(?:hundred|dozen|thousand|million|billion)\b", work, re.I)
            if nums:
                errs.append(("compare.number", ", ".join(repr(n) for n in nums)))
        refused = self.refused_words(s, masks + [(ph[4], ph[5])], [])
        if refused:
            errs.append(("refused_word", ", ".join(sorted(set(refused)))))
        if has_negation(s):
            errs.append(("negation", re.search(NEGATION, _strip_op_negations(s), re.I).group(0)))
        return errs

    def _change(self, f, s, names):
        subj = self.lex.resolve(f["subject"])
        if not self.named(names, subj):
            return [("subject.not_named", f"{f['subject']} is not named")]
        masks = [(a, b) for a, b, c in names if c == subj]
        work = s
        for a, b in masks:
            work = _blank(work, a, b)
        errs = []
        if has_negation(s):
            errs.append(("negation", re.search(NEGATION, _strip_op_negations(s), re.I).group(0)))
        kind = f["from"]["kind"]
        best = None
        for m in re.finditer(r"\b(?:(?P<dir>up|down)\s+)?from\b", work, re.I):
            up_from = re.search(r",\s*(?P<dir>up|down)\s+from\s*$", work[:m.end()], re.I)
            if up_from:
                # "to, up from from": the value before "up from" rose (fell) from the value after it
                to_side = work[:up_from.start()]
                from_side = work[m.end():]
                tv = _last_value(to_side, kind)
                fv = _first_value(from_side, kind)
                trial = self._change_sides(f, fv, tv, up_from.group("dir").lower(), kind)
            else:
                trial = None
                for t in re.finditer(r"\bto\b", work[m.end():], re.I):
                    from_side = work[m.end():m.end() + t.start()]
                    to_side = work[m.end() + t.end():]
                    fv, tv = _first_value(from_side, kind), _first_value(to_side, kind)
                    if fv is None and kind not in ("boolean", "name"):
                        continue
                    trial = self._change_sides(f, fv, tv, (m.group("dir") or "").lower() or None, kind,
                                               from_side, to_side)
                    break
            if trial is not None and (best is None or len(trial) < len(best)):
                best = trial
        if best is None:
            errs.append(("change.phrase", "no change phrase (from … to …, … up from …, … down from …)"))
        else:
            errs += best
        if kind == "boolean" and not words_re(f["attribute"]).search(s):
            errs.append(("yes_no.attribute_words", f"no '{f['attribute'].replace('_', ' ')}' in words"))
        return errs

    def _change_sides(self, f, fv, tv, direction, kind, from_side="", to_side=""):
        errs = []
        if kind == "boolean":
            fv = {"kind": "boolean", "value": not has_negation(from_side)}
            tv = {"kind": "boolean", "value": not has_negation(to_side)}
        if kind == "name":
            fv = f["from"] if self.lex.name_hits(from_side, f["from"]["value"]) else None
            tv = f["to"] if self.lex.name_hits(to_side, f["to"]["value"]) else None
        if not fv or not same_value(fv, f["from"]):
            errs.append(("change.from", f"{_show(f['from'])}: read {_show(fv) if fv else 'nothing'}"))
        if not tv or not same_value(tv, f["to"]):
            errs.append(("change.to", f"{_show(f['to'])}: read {_show(tv) if tv else 'nothing'}"))
        if direction:
            b = bigger(f["to"], f["from"])
            if b is None:
                errs.append(("change.direction", f"'{direction}' with values that have no order"))
            elif (direction == "up") != b:
                errs.append(("change.direction", f"'{direction}' but the value {'rose' if b else 'fell'}"))
        return errs

    # -- a whole claim row ------------------------------------------------------------------------
    def check(self, typ, form, text):
        """[(rule, detail, sentence)]: what the best sentence breaks; [] if one sentence holds the claim."""
        sents = [text[a:b] for a, b in sentences(text)]
        best = None
        for s in sents:
            errs = self.check_sentence(typ, form, s)
            if not errs:
                best = []
                break
            if best is None or _rank(errs) < _rank(best[0]):
                best = (errs, s)
        if best == []:
            if typ == "compare":
                n = sum(len(_phrases(s)) for s in sents)
                if n > 1:
                    return [("compare.second_phrase", "the text holds another compare phrase", text)]
            return []
        errs, s = best
        return [(rule, detail, s) for rule, detail in errs]


def _rank(errs):
    return (any(r.startswith("subject") for r, _ in errs), len(errs))


def _phrases(s):
    """The compare phrases a sentence holds: (family, op, phrase, text, start, end), overlaps resolved
    to the longest, a listed phrase before one with a gap."""
    hits = []
    for fam, op, ph, rx in COMPARE_RES:
        for m in rx.finditer(s):
            hits.append((fam, op, ph, m.group(0), m.start(), m.end(), "…" in ph))
    hits.sort(key=lambda h: (-(h[5] - h[4]), h[6], h[4]))
    kept = []
    for h in hits:
        if all(h[5] <= k[4] or h[4] >= k[5] for k in kept):
            kept.append(h)
    return sorted(kept, key=lambda h: h[4])


def _first_value(side, kind):
    r = Reader(side)
    vals = [v for v in r.values if v["value"]["kind"] == kind and not v["approx"]]
    return vals[0]["value"] if vals else None


def _last_value(side, kind):
    clause = re.split(r"[;:!?•·|]", side)[-1]
    r = Reader(clause)
    vals = [v for v in r.values if v["value"]["kind"] == kind and not v["approx"]]
    return vals[-1]["value"] if vals else None


def _why(v):
    flags = [f for f in ("approx", "range", "negated") if v.get(f)]
    if v.get("op") not in (None, "eq"):
        flags.append("op " + v["op"])
    return f" ({_show(v['value'])}{', ' + ', '.join(flags) if flags else ''})"


def _show(v):
    if not v:
        return "nothing"
    k = v["kind"]
    if k == "money":
        return f"{v['currency']} {v['value']}" + (f"/{v['per']}" if v.get("per") else " one-off")
    if k in ("quantity", "duration"):
        return f"{v['value']} {v['unit']}"
    if k == "percent":
        return f"{v['value']}%"
    return f"{k} {v['value']}"


# --------------------------------------------------------------------------------------------
# The table (contracts/README.md) and the schemas

def schema_validator():
    import jsonschema
    from referencing import Registry, Resource
    with open(os.path.join(CONTRACTS, "entry.schema.json"), encoding="utf-8") as f:
        entry = json.load(f)
    with open(os.path.join(CONTRACTS, "claimed_value.schema.json"), encoding="utf-8") as f:
        value = json.load(f)
    reg = Registry().with_resources([(entry["$id"], Resource.from_contents(entry)),
                                     (value["$id"], Resource.from_contents(value))])
    return jsonschema.Draft202012Validator(entry, registry=reg)


def lexicon_rules(lex, typ, f):
    """The facts a form names must exist: a subject an entity has, an attribute the subject has."""
    errs = []

    def fact(subject, attribute, what):
        c = lex.resolve(subject)
        if not c:
            errs.append(("lexicon.subject", f"{what}: no entity {subject!r}"))
        elif attribute not in lex.entities[c]:
            errs.append(("lexicon.attribute", f"{what}: {c} has no attribute {attribute!r}"))

    if typ in ("fact", "change", "at_event"):
        fact(f["subject"], f["attribute"], "subject")
    if typ == "at_event":
        ev = lex.resolve(f["event"])
        if not ev:
            errs.append(("lexicon.event", f"no event {f['event']!r}"))
        elif "date" not in lex.entities[ev]:
            errs.append(("lexicon.event", f"{ev} has no date"))
    if typ == "compare":
        fact(f["left"]["subject"], f["left"]["attribute"], "left")
        fact(f["right"]["subject"], f["right"]["attribute"], "right")
    if typ == "relation":
        fact(f["subject"], f["link"], "link")
        fact(f["target"], f["attribute"], "target")
    return errs


def style_notes(lex, typ, f, text):
    """A subject named in another case or spacing than the lexicon writes it: valid, but worth a look."""
    out = []
    for key in ("subject", "event", "target"):
        if key in f:
            c = lex.resolve(f[key])
            spellings = [sp for sp, cc in lex.spellings if cc == c]
            if c and not any(re.search(r"(?<![\w])" + re.escape(sp) + r"(?![\w])", text) for sp in spellings):
                if any(re.search(r"(?<![\w])" + re.escape(sp) + r"(?![\w])", text, re.I) for sp in spellings):
                    out.append(f"{key} {c!r} not written as the lexicon writes it")
    return out


def check_table(path, lex, kinds, input_texts=None):
    """(rejections [(id, rule, detail, sentence)], style notes [(id, note)], number of claims)."""
    validator = schema_validator()
    ref = Referee(lex, kinds)
    rejections, notes = [], []
    seen = set()
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    claims = [r for r in rows if (r.get("type") or "").strip()]
    for r in claims:
        rid, typ, text = r.get("id", ""), r["type"].strip(), r.get("text") or ""

        def reject(rule, detail, sentence=""):
            rejections.append((rid, rule, detail, sentence))

        if rid in seen:
            reject("table.id", "id used twice")
        seen.add(rid)
        label = (r.get("label") or "").strip()
        if label not in ("", "true"):
            reject("table.label", f"label {label!r}: every claim must be true")
        try:
            form = json.loads(r.get("form") or "")
        except ValueError as e:
            reject("table.form_json", str(e))
            continue
        try:
            conf = float(r.get("confidence"))
        except (TypeError, ValueError):
            conf = None
        entry = {"id": rid, "type": typ, "text": text, "form": form, "tag": "true",
                 "confidence": conf if conf is not None else r.get("confidence")}
        errs = sorted(validator.iter_errors(entry), key=lambda e: list(e.path))
        if errs:
            for e in errs[:3]:
                reject("schema", f"{'/'.join(str(p) for p in e.path) or 'entry'}: {e.message[:160]}")
            continue
        if input_texts is not None and text.strip() in input_texts:
            reject("table.not_new", "the text is a row of the input")
        lx = lexicon_rules(lex, typ, form)
        for rule, detail in lx:
            reject(rule, detail)
        if lx:
            continue
        for rule, detail, sentence in ref.check(typ, form, text):
            reject("text." + rule, detail, sentence)
        notes += [(rid, n) for n in style_notes(lex, typ, form, text)]
    if len(claims) != 1000:
        rejections.append(("(table)", "table.count", f"{len(claims)} claims, not exactly 1,000", ""))
    return rejections, notes, len(claims)


def attribute_kinds(practice_path):
    kinds = defaultdict(set)
    if practice_path and os.path.exists(practice_path):
        with open(practice_path, encoding="utf-8-sig", newline="") as fh:
            for r in csv.DictReader(fh):
                for f in json.loads(r.get("form") or "[]"):
                    kinds[f["attribute"]].add(f["value"]["kind"])
    return kinds


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("output")
    ap.add_argument("--lexicon", default=os.path.join(ROOT, "data", "lexicon.json"))
    ap.add_argument("--input", help="the run's input csv: no claim may be one of its rows")
    ap.add_argument("--practice", default=os.path.join(ROOT, "data", "practice.csv"))
    args = ap.parse_args()
    with open(args.lexicon, encoding="utf-8") as f:
        lex = Lexicon(json.load(f))
    input_texts = None
    if args.input:
        with open(args.input, encoding="utf-8-sig", newline="") as f:
            input_texts = {r["text"].strip() for r in csv.DictReader(f)}
    rejections, notes, n = check_table(args.output, lex, attribute_kinds(args.practice), input_texts)
    with open(args.output, encoding="utf-8-sig", newline="") as fh:
        text_of = {r["id"]: r.get("text", "") for r in csv.DictReader(fh) if (r.get("type") or "").strip()}
    for rid, rule, detail, sentence in rejections:
        print(f"REJECT {rid}  [{rule}] {detail}")
        print(f"       {sentence or text_of.get(rid, '')}")
    if notes:
        print(f"\nstyle notes (valid, not rejected): {len(notes)}")
        for rid, note in notes[:50]:
            print(f"  {rid}: {note}")
    by_rule = Counter(rule for _, rule, _, _ in rejections)
    bad = len({rid for rid, *_ in rejections if rid != "(table)"})
    print(f"\n{n} claims, {bad} rejected" + (":" if by_rule else "."))
    for rule, k in by_rule.most_common():
        print(f"  {k:5}  {rule}")
    return 1 if rejections else 0


if __name__ == "__main__":
    sys.exit(main())
