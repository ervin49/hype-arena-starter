"""Values -> text, in the forms contracts/value-forms.md reads.

render_value(value) -> str, or None when we cannot write the value so it reads back exactly.
The validator reads every rendered text back with an independent parser (arena.values).
"""
import re

MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July", "August",
               "September", "October", "November", "December"]
CURRENCY_SYMBOLS = {"EUR": "€", "USD": "$", "GBP": "£"}
PHYSICAL_UNITS = {"B", "KB", "MB", "GB", "TB", "mm", "cm", "m", "km", "in", "g", "kg",
                  "mAh", "Hz", "kHz", "MHz", "GHz", "mW", "W", "kW"}
SPELLED_UNITS = {"inch": ("inch", "inches")}
DURATION_WORDS = {"ms": ("millisecond", "milliseconds"), "s": ("second", "seconds"),
                  "min": ("minute", "minutes"), "h": ("hour", "hours"), "day": ("day", "days"),
                  "week": ("week", "weeks"), "month": ("month", "months"), "year": ("year", "years")}
IRREGULAR_PLURALS = {"person": "people", "child": "children", "analysis": "analyses"}


def number(v):
    """Digits with commas between thousands and a decimal point. None if ambiguous to the reader."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    if float(v).is_integer():
        return f"{int(v):,}"
    if round(v, 4) != v:  # 0.857142… weeks: no exact written form
        return None
    text = f"{v:,.4f}".rstrip("0")
    decimals = text.split(".")[1]
    if len(decimals) == 3:  # 1.500 reads as nothing; only a percent may have three decimals
        return None
    return text


def plural(noun):
    if noun in IRREGULAR_PLURALS:
        return IRREGULAR_PLURALS[noun]
    if re.search(r"[^aeiou]y$", noun):
        return noun[:-1] + "ies"
    if re.search(r"(s|x|z|ch|sh)$", noun):
        return noun + "es"
    return noun + "s"


def render_date(iso):
    parts = iso.split("-")
    if len(parts) == 1:
        return parts[0]
    month = MONTH_NAMES[int(parts[1]) - 1]
    if len(parts) == 2:
        return f"{month} {parts[0]}"
    return f"{int(parts[2])} {month} {parts[0]}"


def render_value(v):
    if not isinstance(v, dict) or "op" in v:
        return None
    kind = v.get("kind")
    if kind == "quantity":
        n, unit = number(v["value"]), v["unit"]
        if n is None:
            return None
        if unit in PHYSICAL_UNITS:
            return f"{n} {unit}"
        if unit in SPELLED_UNITS:
            one, many = SPELLED_UNITS[unit]
            return f"{n} {one if v['value'] == 1 else many}"
        return f"{n} {unit if v['value'] == 1 else plural(unit)}"
    if kind == "money":
        if v.get("currency") == "EUR" or v.get("currency") in CURRENCY_SYMBOLS:
            n = number(v["value"])
            text = None if n is None else CURRENCY_SYMBOLS[v["currency"]] + n
        else:
            n = number(v["value"])
            text = None if n is None else f"{v['currency']} {n}"
        if text and v.get("per"):
            text += f" per {v['per']}"
        return text
    if kind == "percent":
        if isinstance(v["value"], bool) or not isinstance(v["value"], (int, float)) or round(v["value"], 4) != v["value"]:
            return None
        n = f"{int(v['value'])}" if float(v["value"]).is_integer() else f"{v['value']:.4f}".rstrip("0")
        return f"{n}%"
    if kind == "date":
        return render_date(v["value"])
    if kind == "version":
        return f"version {v['value']}"
    if kind == "duration":
        n = number(v["value"])
        if n is None or v["unit"] not in DURATION_WORDS:
            return None
        one, many = DURATION_WORDS[v["unit"]]
        return f"{n} {one if v['value'] == 1 else many}"
    if kind == "name":
        return v["value"].strip() or None
    return None  # booleans are written by the templates, as words and polarity
