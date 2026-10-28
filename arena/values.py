"""Value parsing and comparison, following contracts/value-forms.md.

parse_values(text) finds every value written in a text and returns spans:
    {"value": {...claimed value...}, "start": int, "end": int, "raw": str,
     "approx": bool, "range": bool, "negated": bool}

The value dicts use the official schema (claimed_value.schema.json), with
"op" when the text writes a comparison. The extractor reads input texts, so
it records approximations and range ends with flags instead of dropping
them; a strict reader (the referee, the claim validator) treats them as
nothing.
"""

import re

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sep": 9, "sept": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11, "december": 12, "dec": 12,
}
_MONTH = (r"(?:January|February|March|April|May|June|July|August|September|October|"
          r"November|December|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sept|Sep|Oct|Nov|Dec)")

_ONES = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine",
         "ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen", "sixteen",
         "seventeen", "eighteen", "nineteen"]
_TENS = ["twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety"]
WORD_NUMBERS = {w: i for i, w in enumerate(_ONES)}
for _i, _t in enumerate(_TENS):
    WORD_NUMBERS[_t] = 20 + 10 * _i
    for _j in range(1, 10):
        WORD_NUMBERS[f"{_t}-{_ONES[_j]}"] = 20 + 10 * _i + _j
        WORD_NUMBERS[f"{_t} {_ONES[_j]}"] = 20 + 10 * _i + _j
_WORDNUM = (r"(?:a\s+dozen|a\s+hundred|(?:" + "|".join(_ONES[1:10]) + r")\s+hundred|"
            + "|".join(sorted(WORD_NUMBERS, key=len, reverse=True)) + ")")

# A run of digits with commas and points; validated by to_number().
_DIG = r"(?<![\w.,])\d(?:[\d,.]*\d)?"
_SCALE = r"(?:\s?(?:thousand|million|billion|bn)\b|(?:M|k)(?![A-Za-z]))"
NUM = rf"(?:{_DIG}|\b{_WORDNUM}\b)(?:{_SCALE})?"
SCALES = {"thousand": 1e3, "k": 1e3, "million": 1e6, "m": 1e6, "billion": 1e9, "bn": 1e9}

NEGATIONS = {"not", "no", "never", "none", "nobody", "nothing", "neither", "nor",
             "without", "cannot"}
_NEG_RE = re.compile(r"\b(?:not|no|never|none|nobody|nothing|neither|nor|without|cannot)\b|\w+n't\b|\w+n’t\b", re.I)
_CLAUSE_END = re.compile(r"[.,;:!?•·|]|\n\s*\n")

_APPROX_BEFORE = re.compile(
    r"(?:\babout|\baround|\bapproximately|\bapprox\.?|\broughly|\bnearly|\balmost|\bcirca|"
    r"\bca\.?|\bsome|\bestimated|\best\.?|\bclose to|\bmore or less|~|≈|±)\s*$", re.I)
_APPROX_AFTER = re.compile(r"^\s*(?:or so\b|give or take\b|-ish\b)", re.I)

_OP_BEFORE = [
    ("le", r"no more than|not more than|up to|at most|maximum|max\.?"),
    ("ge", r"at least|no less than|not less than|no fewer than|minimum"),
    ("gt", r"over|more than|greater than|higher than|above|exceeding|in excess of|upwards of"),
    ("lt", r"under|less than|fewer than|lower than|below"),
]
_OP_BEFORE_RE = [(op, re.compile(rf"\b(?:{p})\s*$", re.I)) for op, p in _OP_BEFORE]
_OP_AFTER = [
    ("le", r"or less|or fewer|or under|or below|or lower|or shorter"),
    ("ge", r"or more|or higher|or above|or longer|or over"),
]
_OP_AFTER_RE = [(op, re.compile(rf"^\s*(?:{p})\b", re.I)) for op, p in _OP_AFTER]
_DATE_OP_BEFORE = [
    ("le", r"no later than|by"), ("ge", r"no earlier than"),
    ("lt", r"before|prior to"), ("gt", r"after"),
]
_DATE_OP_BEFORE_RE = [(op, re.compile(rf"\b(?:{p})\s*$", re.I)) for op, p in _DATE_OP_BEFORE]

CURRENCY_SYMBOLS = {"€": "EUR", "$": "USD", "£": "GBP", "US$": "USD"}
CURRENCY_CODES = ["EUR", "USD", "GBP", "CHF", "RON", "PLN", "CZK", "HUF", "SEK", "NOK",
                  "DKK", "JPY", "CNY", "INR", "CAD", "AUD"]
CURRENCY_WORDS = {"euro": "EUR", "euros": "EUR", "dollar": "USD", "dollars": "USD", "lei": "RON"}

PERIODS = {"month": "month", "mo": "month", "monthly": "month", "day": "day",
           "daily": "day", "week": "week", "wk": "week", "weekly": "week",
           "year": "year", "yr": "year", "yearly": "year", "annually": "year",
           "annum": "year"}
_PERIOD = (r"(?:\s*(?:per\s+user|per\s+seat|/\s*user|/\s*seat|per\s+(?:terabyte|gigabyte|TB|GB)))?"
           r"(?:\s*/\s*(?P<p1>month|mo|day|week|wk|year|yr)\b"
           r"|\s+(?:a|per|each)\s+(?P<p2>month|day|week|year)\b"
           r"|\s+(?P<p3>monthly|daily|weekly|yearly|annually)\b"
           r"|\s+per\s+(?P<p4>annum)\b)?")

# Quantity units: spelling -> (canonical symbol). Case-sensitive symbols first.
QUANTITY_UNITS = {
    "B": "B", "KB": "KB", "kB": "KB", "kb": "KB", "MB": "MB", "mb": "MB", "GB": "GB",
    "gb": "GB", "TB": "TB", "tb": "TB",
    "byte": "B", "bytes": "B", "kilobyte": "KB", "kilobytes": "KB", "megabyte": "MB",
    "megabytes": "MB", "gigabyte": "GB", "gigabytes": "GB", "gig": "GB", "gigs": "GB",
    "terabyte": "TB", "terabytes": "TB",
    "mm": "mm", "cm": "cm", "m": "m", "km": "km",
    "millimetre": "mm", "millimetres": "mm", "millimeter": "mm", "millimeters": "mm",
    "centimetre": "cm", "centimetres": "cm", "centimeter": "cm", "centimeters": "cm",
    "metre": "m", "metres": "m", "meter": "m", "meters": "m",
    "kilometre": "km", "kilometres": "km", "kilometer": "km", "kilometers": "km",
    "inch": "inch", "inches": "inch", '"': "inch", "″": "inch", "in": "inch",
    "g": "g", "kg": "kg", "gram": "g", "grams": "g", "gramme": "g", "grammes": "g",
    "kilogram": "kg", "kilograms": "kg", "kilo": "kg", "kilos": "kg",
    "mAh": "mAh",
    "Hz": "Hz", "kHz": "kHz", "MHz": "MHz", "GHz": "GHz", "hertz": "Hz",
    "kilohertz": "kHz", "megahertz": "MHz", "gigahertz": "GHz",
    "mW": "mW", "W": "W", "kW": "kW", "milliwatt": "mW", "milliwatts": "mW",
    "watt": "W", "watts": "W", "kilowatt": "kW", "kilowatts": "kW",
}
_CASE_SENSITIVE_UNITS = {"B", "KB", "kB", "kb", "MB", "mb", "GB", "gb", "TB", "tb", "mm", "cm",
                         "m", "km", "in", "g", "kg", "mAh", "Hz", "kHz", "MHz", "GHz", "mW", "W", "kW"}
UNIT_BASE = {  # canonical unit -> (dimension, factor to base)
    "B": ("data", 1), "KB": ("data", 1e3), "MB": ("data", 1e6), "GB": ("data", 1e9),
    "TB": ("data", 1e12),
    "mm": ("length", 1e-3), "cm": ("length", 1e-2), "m": ("length", 1), "km": ("length", 1e3),
    "in": ("length", 0.0254), "inch": ("length", 0.0254),
    "g": ("mass", 1), "kg": ("mass", 1e3), "mAh": ("charge", 1),
    "Hz": ("freq", 1), "kHz": ("freq", 1e3), "MHz": ("freq", 1e6), "GHz": ("freq", 1e9),
    "mW": ("power", 1e-3), "W": ("power", 1), "kW": ("power", 1e3),
}

DURATION_UNITS = {
    "ms": "ms", "millisecond": "ms", "milliseconds": "ms",
    "s": "s", "sec": "s", "secs": "s", "second": "s", "seconds": "s",
    "min": "min", "mins": "min", "minute": "min", "minutes": "min",
    "h": "h", "hr": "h", "hrs": "h", "hour": "h", "hours": "h",
    "d": "day", "day": "day", "days": "day",
    "week": "week", "weeks": "week", "wk": "week", "wks": "week",
    "fortnight": "fortnight", "fortnights": "fortnight",
    "month": "month", "months": "month", "mo": "month", "mth": "month", "mths": "month",
    "year": "year", "years": "year", "yr": "year", "yrs": "year",
    "decade": "decade", "decades": "decade",
}
DURATION_SECONDS = {"ms": 1e-3, "s": 1, "min": 60, "h": 3600, "day": 86400, "week": 604800}
DURATION_MONTHS = {"month": 1, "year": 12}
_A_AS_ONE = r"(?:under|within|in|for|over|than|at least|at most|to|only|just|about|around)"


def to_number(raw, decimal_comma=False):
    """Read a digit run as value-forms.md does; None when it is ambiguous."""
    if "," in raw and "." in raw:
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+\.\d+", raw):
            return float(raw.replace(",", ""))
        return None
    if "," in raw:
        if re.fullmatch(r"\d{1,3}(?:,\d{3})+", raw):
            return float(raw.replace(",", ""))
        if decimal_comma and re.fullmatch(r"\d+,\d{1,2}", raw):
            return float(raw.replace(",", "."))
        return None
    if raw.count(".") > 1:
        return None
    return float(raw)


def read_number(s, decimal_comma=False, allow_three_decimals=False):
    """Read NUM (digits or words, with an optional scale)."""
    s = s.strip()
    m = re.fullmatch(rf"(?P<n>.+?)\s?(?P<sc>thousand|million|billion|bn|M|k)?", s, re.S)
    n, sc = m.group("n").strip(), m.group("sc")
    if n.lower() in ("a", "an"):
        return None
    low = re.sub(r"\s+", " ", n.lower())
    if low == "a dozen":
        v = 12.0
    elif low == "a hundred":
        v = 100.0
    elif low.endswith(" hundred") and low.split()[0] in WORD_NUMBERS:
        v = 100.0 * WORD_NUMBERS[low.split()[0]]
    elif low in WORD_NUMBERS:
        v = float(WORD_NUMBERS[low])
    elif re.fullmatch(r"\d[\d,.]*", n):
        if (not allow_three_decimals and re.fullmatch(r"\d+\.\d{3}", n)):
            return None
        v = to_number(n, decimal_comma)
        if v is None:
            return None
    else:
        return None
    if sc:
        v *= SCALES[sc.lower()]
    return v


def clean_number(v):
    if isinstance(v, float) and v.is_integer() and abs(v) < 1e15:
        return int(v)
    return round(v, 9) if isinstance(v, float) else v


def singular(word):
    w = word.lower()
    if w in ("people", "persons"):
        return "person"
    if w in ("children",):
        return "child"
    if w in ("men",):
        return "man"
    if w in ("women",):
        return "woman"
    if len(w) > 3 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and re.search(r"(?:ss|sh|ch|x|z)es$", w):
        return w[:-2]
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


# Words that follow a number but are not a counted noun.
_NOT_NOUNS = {"of", "our", "the", "a", "an", "and", "or", "to", "in", "on", "at", "for",
              "per", "by", "with", "from", "than", "more", "less", "new", "percent",
              "per", "cent", "is", "are", "was", "were", "it", "its", "this", "that",
              "has", "have", "had", "will", "be", "so", "as", "times", "x", "plus",
              "into", "across", "over", "under", "after", "before", "out", "up", "down",
              "all", "but", "now", "still", "while", "which", "who", "we", "they", "he",
              "she", "you", "i", "their", "his", "her", "my", "your", "each", "every",
              "about", "around", "since", "until", "when", "if", "then", "also", "only",
              "just", "even", "already"}


def _mask(text, start, end):
    return text[:start] + " " * (end - start) + text[end:]


def _clause_start(text, pos):
    best = 0
    for m in _CLAUSE_END.finditer(text, 0, pos):
        best = m.end()
    return best


_NOT_NEGATION = re.compile(
    r"\b(?:no|not)\s+(?:more|less|fewer|later|earlier)\s+than\b", re.I)


def is_negated_before(text, pos):
    """A negation word earlier in the clause that ends before pos.

    Comparison words such as "no more than" are part of their value."""
    seg = _NOT_NEGATION.sub(" ", text[_clause_start(text, pos):pos])
    return bool(_NEG_RE.search(seg))


def has_negation(text):
    return bool(_NEG_RE.search(text))


def _flags(text, start, end):
    before, after = text[max(0, start - 40):start], text[end:end + 30]
    approx = bool(_APPROX_BEFORE.search(before) or _APPROX_AFTER.search(after))
    # "1 or 2 days" is a range; "€49 a month or €490 a year" is a choice, and
    # both of its values read: "or" joins a range only after a bare number.
    # "10 GB to 20 GB" is a range at both ends, but "from 10 GB to 20 GB" is a
    # change, whose values read.
    change = re.search(r"\bfrom\s+\S*\d[\d,.]*\s*[A-Za-z%]*\s+to\s+\S*$", before, re.I)
    rng = bool(re.search(r"\bbetween\s+$", before, re.I)
               or re.search(r"\bbetween\s+\S+\s+and\s+$", before, re.I)
               or re.search(r"\d\s*(?:-|–|—|to)\s*\S*$", before)
               or re.search(r"(?<![\w.,])\d[\d,.]*\s+or\s+\S*$", before)
               or (re.search(r"\d[\d,.]*\s*[A-Za-z%]+\s+to\s+\S*$", before) and not change)
               or re.match(r"^\s*(?:-|–|—)\s*\S?\d|^\s*to\s+\S?\d", after)
               or re.match(r"^\s*and\s+\S?\d", after) and re.search(r"\bbetween\s+\S*$", before, re.I))
    return approx, rng


def _op(text, start, end, date=False, duration=False):
    before, after = text[max(0, start - 40):start], text[end:end + 20]
    if duration and re.search(r"\bwithin\s*$", before, re.I):
        return "le"
    table = _DATE_OP_BEFORE_RE if date else _OP_BEFORE_RE
    for op, rx in table:
        if rx.search(before):
            return op
    if not date:
        if after.startswith("+"):
            return "ge"
        for op, rx in _OP_AFTER_RE:
            if rx.search(after):
                return op
    return None


def _date_value(y, mo=None, d=None):
    y = int(y)
    if not 1900 <= y <= 2099:
        return None
    if mo is None:
        return f"{y:04d}"
    mo = int(mo)
    if not 1 <= mo <= 12:
        return None
    if d is None:
        return f"{y:04d}-{mo:02d}"
    d = int(d)
    import calendar
    if not 1 <= d <= calendar.monthrange(y, mo)[1]:
        return None
    return f"{y:04d}-{mo:02d}-{d:02d}"


def parse_values(text, skip_spans=()):
    """Every value written in text, in reading order.

    skip_spans: (start, end) ranges, such as subject names, whose characters
    state no value ("the 2026 of Hooly I/O 2026 states no year").
    """
    out = []
    work = text
    for s, e in skip_spans:
        work = _mask(work, s, e)

    def add(value, start, end, mask=True, date=False, op=True, op_end=None):
        nonlocal work
        if op:
            o = _op(text, start, end, date=date, duration=value["kind"] == "duration")
            if not o and op_end and text[op_end:op_end + 1] == "+":
                o = "ge"
            if o:
                value["op"] = o
        approx, rng = _flags(text, start, end)
        out.append({"value": value, "start": start, "end": end, "raw": text[start:end],
                    "approx": approx, "range": rng,
                    "negated": is_negated_before(text, start)})
        if mask:
            work = _mask(work, start, end)

    # 1. ISO dates.
    for m in re.finditer(r"(?<![\w.-])(\d{4})-(\d{2})(?:-(\d{2}))?(?![\w-])", work):
        v = _date_value(m.group(1), m.group(2), m.group(3))
        if v:
            add({"kind": "date", "value": v}, m.start(), m.end(), date=True)
    # 2. Written dates.
    pats = [
        rf"(?:\bthe\s+)?\b(?P<d>\d{{1,2}})(?:st|nd|rd|th)?(?:\s+of)?\s*(?P<m>{_MONTH})\b\.?,?\s+(?P<y>\d{{4}})\b",
        rf"\b(?P<m>{_MONTH})\b\.?\s+(?P<d>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y>\d{{4}})\b",
        rf"\b(?P<m>{_MONTH})\b\.?,?\s+(?P<y>\d{{4}})\b",
    ]
    for p in pats:
        for m in re.finditer(p, work):
            mon = m.group("m")
            if mon == "may" or (mon.lower() == "may" and mon != "May"):
                continue
            d = m.groupdict().get("d")
            v = _date_value(m.group("y"), MONTHS[mon.lower().rstrip(".")], d)
            if v:
                add({"kind": "date", "value": v}, m.start(), m.end(), date=True)
    # 3. Money.
    codes = "|".join(CURRENCY_CODES)
    money_pats = [
        rf"(?P<cur>US\$|€|\$|£)\s?(?P<num>{_DIG}(?:{_SCALE})?)",
        rf"\b(?P<cur>{codes})\s?(?P<num>{_DIG}(?:{_SCALE})?)",
        rf"(?P<num>{NUM})\s?(?P<cur>{codes}|euros?|dollars?|lei|€)\b",
    ]
    for p in money_pats:
        for m in re.finditer(p + _PERIOD, work):
            v = read_number(m.group("num"), decimal_comma=True, allow_three_decimals=False)
            if v is None:
                continue
            cur = m.group("cur")
            cur = CURRENCY_SYMBOLS.get(cur) or CURRENCY_WORDS.get(cur.lower()) or cur.upper()
            val = {"kind": "money", "value": clean_number(v), "currency": cur}
            per = next((m.group(g) for g in ("p1", "p2", "p3", "p4") if m.group(g)), None)
            if per:
                val["per"] = PERIODS[per.lower()]
            add(val, m.start(), m.end())
    # 4. Percent.
    for m in re.finditer(rf"(?P<num>{NUM})\s?(?:%|percent\b|per\s+cent\b)", work, re.I):
        v = read_number(m.group("num"), allow_three_decimals=True)
        if v is not None:
            add({"kind": "percent", "value": clean_number(v)}, m.start(), m.end())
    # 5. Versions.
    for m in re.finditer(r"(?:\bv|\bversion\s+|\bver\.?\s*)(\d+(?:\.\d+)*)\b(?!\.\d)", work, re.I):
        add({"kind": "version", "value": m.group(1)}, m.start(), m.end(), op=False)
    for m in re.finditer(r"(?<![\w.,])(\d+\.\d+\.\d+(?:\.\d+)*)(?![\w.]|\.\d)", work):
        add({"kind": "version", "value": m.group(1)}, m.start(), m.end(), op=False)
    # 6. Durations.
    dunits = "|".join(sorted(DURATION_UNITS, key=len, reverse=True))
    for m in re.finditer(rf"(?P<num>{NUM})(?:\s?-\s?|\s?)(?P<u>{dunits})(?![A-Za-z])", work, re.I):
        u = m.group("u")
        if len(u) == 1 and u != u.lower():
            continue
        v = read_number(m.group("num"))
        if v is None:
            continue
        unit = DURATION_UNITS[u.lower()]
        if unit == "fortnight":
            v, unit = v * 2, "week"
        elif unit == "decade":
            v, unit = v * 10, "year"
        add({"kind": "duration", "value": clean_number(v), "unit": unit}, m.start(), m.end())
    for m in re.finditer(rf"\b(?P<pre>{_A_AS_ONE})\s+(?P<a>an?)\s+(?P<u>fortnight|millisecond|second|minute|hour|day|week|month|year|decade)\b", work, re.I):
        unit = DURATION_UNITS[m.group("u").lower()]
        v = 1
        if unit == "fortnight":
            v, unit = 2, "week"
        elif unit == "decade":
            v, unit = 10, "year"
        add({"kind": "duration", "value": v, "unit": unit}, m.start("a"), m.end())
    # 7. Quantities with a unit.
    qunits = "|".join(re.escape(u) for u in sorted(QUANTITY_UNITS, key=len, reverse=True))
    for m in re.finditer(rf"(?P<num>{NUM})(?:\s?-\s?|\s?)(?P<u>{qunits})(?![A-Za-z0-9])", work, re.I):
        u = m.group("u")
        if u in QUANTITY_UNITS and (u in _CASE_SENSITIVE_UNITS or u in ('"', "″")):
            unit = QUANTITY_UNITS[u]
        elif u.lower() in QUANTITY_UNITS and u.lower() not in _CASE_SENSITIVE_UNITS:
            unit = QUANTITY_UNITS[u.lower()]
        else:
            continue
        if u in ('"', "″") and m.group(0)[-2:-1].isspace():
            continue
        if u == "in" and re.match(r"\s+\w", work[m.end():]):
            continue  # "3 in Europe"
        v = read_number(m.group("num"))
        if v is None:
            continue
        add({"kind": "quantity", "value": clean_number(v), "unit": unit}, m.start(), m.end())
    # The name is part of the value: "Hooly Gemini 2.2". Read from text, since
    # names are masked in work.
    for m in re.finditer(r"\b[A-Z][\w/]*\s(\d+\.\d+)(?!\d|\.\d|\s?%)", text):
        s, e = m.start(1), m.end(1)
        if work[s:e] == text[s:e]:
            # "Hooly Maps 4.5 stars" is a count: keep both readings when a
            # word follows, and let the extractor choose.
            alt = bool(re.match(r"\s+[A-Za-z]", text[e:]))
            add({"kind": "version", "value": m.group(1)}, s, e, op=False, mask=not alt)
            if alt:
                out[-1]["alt"] = True
    # 8. Plain years (a four-digit number from 1900 to 2099).
    for m in re.finditer(r"(?<![\w.,$€£-])(19\d{2}|20\d{2})(?![\w,]|\.\d)", work):
        if re.search(r"\b[QH][1-4]\s*$", work[:m.start()]):
            continue
        add({"kind": "date", "value": m.group(1)}, m.start(), m.end(), date=True)
    # 9. Counted nouns: a number, up to two words, then the noun.
    for m in re.finditer(rf"(?P<num>{NUM})(?P<plus>\+)?(?P<rest>(?:\s+[A-Za-z][\w'’-]*){{1,3}})", work, re.I):
        v = read_number(m.group("num"))
        if v is None:
            continue
        words = re.findall(r"[A-Za-z][\w'’-]*", m.group("rest"))
        noun, end = None, m.end("num")
        pos = m.end("plus") if m.group("plus") else m.end("num")
        spans = [(w.start(), w.end(), w.group(0))
                 for w in re.finditer(r"[A-Za-z][\w'’-]*", work[pos:m.end()])]
        cands = []
        for i, (s, e, w) in enumerate(spans[:3]):
            lw = w.lower()
            if lw in ("of", "our", "the") and i < 2:
                continue
            if lw in _NOT_NOUNS or lw in NEGATIONS:
                break
            cands.append((s, e, w))
        plural = [c for c in cands if _looks_plural(c[2].lower())]
        if cands:
            s, e, noun = (plural or cands)[0]
            end = pos + e
        if not noun:
            continue
        unit = singular(noun.strip("'’-"))
        add({"kind": "quantity", "value": clean_number(v), "unit": unit}, m.start(), end,
            op_end=m.end("num"))
        if any(o.get("alt") and o["start"] == m.start() for o in out[:-1]):
            out[-1]["alt"] = True
    out.sort(key=lambda x: x["start"])
    return out


def _looks_plural(w):
    return w in ("people",) or (len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")))


# ---------------------------------------------------------------- comparison

def norm_name(s):
    return re.sub(r"[\s\-_.]+", "", str(s).lower())


def canonical_amount(v):
    """(family, magnitude) used to compare two values of one kind, or None."""
    k = v.get("kind")
    if k == "quantity":
        u = v.get("unit")
        if u in UNIT_BASE:
            dim, f = UNIT_BASE[u]
            return (("q", dim), float(v["value"]) * f)
        return (("q", "count", singular(str(u))), float(v["value"]))
    if k == "duration":
        u = v.get("unit")
        if u in DURATION_SECONDS:
            return (("d", "time"), float(v["value"]) * DURATION_SECONDS[u])
        if u in DURATION_MONTHS:
            return (("d", "months"), float(v["value"]) * DURATION_MONTHS[u])
        return None
    if k == "money":
        return (("m", v.get("currency"), v.get("per")), float(v["value"]))
    if k == "percent":
        return (("p",), float(v["value"]))
    return None


def _close(a, b):
    return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))


def values_equal(a, b):
    """Whether two exact values state the same thing (units convert)."""
    if a.get("kind") != b.get("kind"):
        return False
    k = a["kind"]
    if k in ("quantity", "duration", "money", "percent"):
        ca, cb = canonical_amount(a), canonical_amount(b)
        return bool(ca and cb and ca[0] == cb[0] and _close(ca[1], cb[1]))
    if k == "date":
        return a["value"] == b["value"]
    if k == "version":
        return str(a["value"]) == str(b["value"])
    if k == "name":
        return norm_name(a["value"]) == norm_name(b["value"])
    if k == "boolean":
        return a["value"] is b["value"] or a["value"] == b["value"]
    return a == b


def comparable(a, b):
    """Same kind and family, so that one can be ordered against the other."""
    if a.get("kind") != b.get("kind"):
        return False
    if a["kind"] == "date":
        return True
    ca, cb = canonical_amount(a), canonical_amount(b)
    return bool(ca and cb and ca[0] == cb[0])


def date_interval(s):
    """A partial ISO date as its first and last day, as strings."""
    import calendar
    parts = s.split("-")
    if len(parts) == 1:
        return f"{s}-01-01", f"{s}-12-31"
    if len(parts) == 2:
        y, m = int(parts[0]), int(parts[1])
        return f"{s}-01", f"{s}-{calendar.monthrange(y, m)[1]:02d}"
    return s, s


def dates_compatible(a, b):
    """Two partial dates that can name the same day ("2025-11" and "2025-11-03")."""
    a0, a1 = date_interval(a)
    b0, b1 = date_interval(b)
    return a0 <= b1 and b0 <= a1


def compatible(a, b):
    """Equal, or not distinguishable (dates of different precision)."""
    if values_equal(a, b):
        return True
    if a.get("kind") == b.get("kind") == "date":
        return dates_compatible(a["value"], b["value"])
    return False


def satisfies(exact, constraint):
    """Whether an exact value meets a value with an op; None if they do not compare."""
    op = constraint.get("op") or "eq"
    if not comparable(exact, constraint):
        return None
    if exact["kind"] == "date":
        x0, x1 = date_interval(exact["value"])
        c0, c1 = date_interval(constraint["value"])
        checks = {"lt": x1 < c0, "le": x1 <= c1, "gt": x0 > c1, "ge": x0 >= c0,
                  "eq": dates_compatible(exact["value"], constraint["value"])}
        if checks[op]:
            return True
        # wholly on the wrong side
        neg = {"lt": x0 >= c0, "le": x0 > c1, "gt": x1 <= c1, "ge": x1 < c0,
               "eq": not dates_compatible(exact["value"], constraint["value"])}
        return False if neg[op] else None
    x, c = canonical_amount(exact)[1], canonical_amount(constraint)[1]
    return {"lt": x < c and not _close(x, c), "le": x <= c or _close(x, c),
            "gt": x > c and not _close(x, c), "ge": x >= c or _close(x, c),
            "eq": _close(x, c)}[op]
