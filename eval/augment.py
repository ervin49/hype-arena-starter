"""Synthetic lies: false rows made from true practice rows, one fact changed.

The engine sees 1,581 true rows and only 277 false ones. C measured how the
real false facts lie (out-of-fold extractor): 151 state a value that was never
true, 103 are stale (an older value stated later), 67 are too early (a later
value stated before it happened). This makes more of the same kinds:

- wrong:  the number, date, version or name perturbed to a value the fact
          never had (x1.2, a few days off, another name of the same attribute);
- stale:  the value the same fact had BEFORE the row's date;
- early:  the value it had AFTER the row's date.

The text is rewritten where it states the value, in a form
contracts/value-forms.md reads, and read back with arena.values: a synthetic
row is kept only when its new text states the new value and no longer states
the old one. It keeps its source row's date; "source" names that row, so a
caller can put it in the source's fold and page.

    from augment import augment
    synth = augment(rows, lexicon, n=277)   # rows: the labelled rows it may learn from
"""

import json
import random
import re
from collections import defaultdict
from datetime import date, timedelta

import common  # noqa: F401  (puts the repository on sys.path)
from arena.values import canonical_amount, compatible, norm_name, parse_values, values_equal

# The real mix of the lies we can make (the 32 ambiguous and 7 unknown-fact ones aside).
MIX = {"wrong": 151, "stale": 103, "early": 67}
AMOUNTS = ("quantity", "duration", "money", "percent")
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
NUMBER = re.compile(r"\d[\d,]*(?:\.\d+)?")


def _facts(row):
    return json.loads(row["form"]) if row.get("form") else []


def timelines(rows):
    """(subject, attribute) -> [(date, value)] from the true rows, by date."""
    out = defaultdict(list)
    for r in rows:
        if r.get("label") == "true":
            for f in _facts(r):
                out[(f["subject"], f["attribute"])].append((r["date"], f["value"]))
    for v in out.values():
        v.sort(key=lambda dv: dv[0])
    return out


def _aliases(lexicon):
    """Normalised name -> every spelling the lexicon lists for it."""
    out = {}
    for s in lexicon.get("subjects", []):
        names = [s["name"]] + list(s.get("aliases") or [])
        out[norm_name(s["name"])] = names
    return out


def stated(text, value, aliases):
    """[(start, end, raw)] of every place the text states value plainly."""
    if value["kind"] == "name":
        spellings = aliases.get(norm_name(value["value"]), [value["value"]])
        return [(m.start(), m.end(), m.group(0)) for s in spellings
                for m in re.finditer(r"(?<!\w)" + re.escape(s) + r"(?!\w)", text, re.I)]
    return [(v["start"], v["end"], v["raw"]) for v in parse_values(text)
            if not (v["approx"] or v["range"] or v["negated"] or v.get("alt"))
            and v["value"].get("kind") == value["kind"] and compatible(v["value"], value)]


def locate(text, value, aliases):
    """(start, end, raw) of the one place the text states value, or None."""
    hits = stated(text, value, aliases)
    return hits[0] if len(hits) == 1 else None


def _fmt(x, decimals):
    if abs(x - round(x)) < 1e-9:
        return f"{int(round(x)):,}"
    return f"{x:,.{decimals}f}".rstrip("0").rstrip(".")


def _render_date(raw, iso):
    parts = [int(p) for p in iso.split("-")]
    if re.fullmatch(r"\d{4}(-\d{2}){0,2}", raw.strip()):
        return iso
    if len(parts) == 1:
        return str(parts[0])
    month = MONTHS[parts[1] - 1]
    if len(parts) == 2:
        return f"{month} {parts[0]}"
    return f"{month} {parts[2]}, {parts[0]}" if raw[:1].isalpha() else f"{parts[2]} {month} {parts[0]}"


def _shift_date(iso, rng):
    parts = iso.split("-")
    if len(parts) == 3:
        d = date.fromisoformat(iso) + timedelta(days=rng.choice([-21, -14, -10, -7, -5, -3, 3, 5, 7, 10, 14, 21]))
        return d.isoformat()
    if len(parts) == 2:
        y, m = int(parts[0]), int(parts[1]) - 1 + rng.choice([-3, -2, -1, 1, 2, 3])
        return f"{y + m // 12:04d}-{m % 12 + 1:02d}"
    return str(int(parts[0]) + rng.choice([-1, 1]))


def _rewrite(text, span, kind, new_raw_for):
    """The text with the span's value replaced, or None."""
    s, e, raw = span
    new = new_raw_for(raw)
    return None if new is None or new == raw else text[:s] + new + text[e:]


def _number_raws(raw, value, targets, rng):
    """(new raw, factor) for amounts: the number in raw scaled to each target factor."""
    m = NUMBER.search(raw)
    if not m:
        return []
    tok = m.group(0)
    if "," in tok and not re.fullmatch(r"\d{1,3}(,\d{3})+(\.\d+)?", tok):
        return []                                   # a decimal comma: not ours to rewrite
    x = float(tok.replace(",", ""))
    decimals = len(tok.split(".")[1]) if "." in tok else 0
    out = []
    for f in targets:
        y = round(x * f, max(decimals, 2 if x * f < 10 else 0))
        if y <= 0 or abs(y - x) < 1e-9:
            continue
        out.append((raw[:m.start()] + _fmt(y, max(decimals, 1)) + raw[m.end():], y / x))
    return out


def _read_back(new_text, start, kind):
    """The value the new text states from start on, as the engine reads it, or None."""
    for v in parse_values(new_text):
        if v["start"] == start and v["value"].get("kind") == kind:
            if v["approx"] or v["range"] or v["negated"]:
                return None
            return v["value"]
    return None


def _ever_true(key, value, tl):
    return any(compatible(v, value) for _, v in tl.get(key, []))


def candidates(row, fact, lie, tl, aliases, name_pool, rng):
    """[(new text, new value)] for one lie about one fact of a true row."""
    key, val, d = (fact["subject"], fact["attribute"]), fact["value"], row["date"]
    span = locate(row["text"], val, aliases)
    if not span:
        return []
    kind = val["kind"]
    if lie == "wrong":
        if kind in AMOUNTS:
            small = canonical_amount(val) and abs(canonical_amount(val)[1]) <= 20
            factors = [1.2, 0.8, 1.5, 0.75, 2.0, 0.5, 1.25, 0.9]
            rng.shuffle(factors)
            raws = _number_raws(span[2], val, factors, rng)
            if small:
                tok = float(NUMBER.search(span[2]).group(0).replace(",", "")) if NUMBER.search(span[2]) else 0
                raws += _number_raws(span[2], val, [(tok + k) / tok for k in (1, -1, 2) if tok and tok + k > 0], rng)
            targets = [r for r, _ in raws]
        elif kind == "date":
            targets = [_render_date(span[2], _shift_date(val["value"], rng)) for _ in range(4)]
        elif kind == "version":
            parts = str(val["value"]).split(".")
            alts = []
            for k in (1, -1, 2):
                p = parts[:-1] + [str(int(parts[-1]) + k)] if parts[-1].isdigit() and int(parts[-1]) + k >= 0 else None
                if p:
                    alts.append(span[2].replace(str(val["value"]), ".".join(p)))
            targets = alts
        elif kind == "name":
            # another name of the same type: one this attribute takes elsewhere, or a lexicon
            # entity sharing an attribute with the true one (a person for a person)
            kin = name_pool["types"].get(norm_name(val["value"]))
            same_type = [n for n, t in name_pool["types"].items() if kin and t & kin]
            pool = [n for n in name_pool.get(fact["attribute"], []) + sorted(name_pool["names"][k] for k in same_type)
                    if not _ever_true(key, {"kind": "name", "value": n}, tl) and norm_name(n) != norm_name(fact["subject"])]
            targets = list(dict.fromkeys(pool))[:6]
            rng.shuffle(targets)
        else:
            return []
    else:
        hist = tl.get(key, [])
        if lie == "stale":
            olds = [v for dd, v in hist if dd < d and not compatible(v, val)]
            # stated true before, and not again on or after: replaced by now
            olds = [v for v in olds if not any(compatible(v, w) for dd, w in hist if dd >= d)]
            pick = olds[-1:] if olds else []
        else:
            news = [v for dd, v in hist if dd > d and not compatible(v, val)]
            news = [v for v in news if not any(compatible(v, w) for dd, w in hist if dd <= d)]
            pick = news[:1]
        if not pick:
            return []
        want = pick[0]
        if kind in AMOUNTS:
            ca, cw = canonical_amount(val), canonical_amount(want)
            if not (ca and cw and ca[0] == cw[0] and ca[1]):
                return []
            targets = [r for r, _ in _number_raws(span[2], val, [cw[1] / ca[1]], rng)]
        elif kind == "date":
            targets = [_render_date(span[2], want["value"])]
        elif kind == "version":
            targets = [span[2].replace(str(val["value"]), str(want["value"]))]
        elif kind == "name":
            targets = [want["value"]]
        else:
            return []
    out = []
    for raw in targets:
        new_text = _rewrite(row["text"], span, kind, lambda _r, raw=raw: raw)
        if not new_text:
            continue
        if kind == "name":
            new_val = {"kind": "name", "value": raw}
            if stated(new_text, val, aliases):
                continue
        else:
            new_val = _read_back(new_text, span[0], kind)
            if not new_val or stated(new_text, val, aliases):
                continue
        if lie == "wrong" and _ever_true(key, new_val, tl):
            continue
        if lie != "wrong" and not values_equal(new_val, want):
            continue
        out.append((new_text, new_val))
    return out


def augment(rows, lexicon, n, seed=0, mix=None):
    """About n synthetic false rows from the true rows, in the mix of MIX.

    Each is {"id", "text", "date", "label": "false", "form", "source", "lie", "kind"};
    "form" is the source's form with the one fact changed. A source row gives
    at most one lie."""
    mix = mix or MIX
    rng = random.Random(seed)
    tl = timelines(rows)
    aliases = _aliases(lexicon)
    name_pool = defaultdict(list)
    for r in rows:
        if r.get("label") == "true":
            for f in _facts(r):
                if f["value"]["kind"] == "name":
                    name_pool[f["attribute"]].append(f["value"]["value"])
    for k in name_pool:
        name_pool[k] = sorted(set(name_pool[k]))
    name_pool["types"] = {norm_name(e["name"]): frozenset(e.get("attributes") or []) for e in lexicon.get("subjects", [])}
    name_pool["names"] = {norm_name(e["name"]): e["name"] for e in lexicon.get("subjects", [])}
    texts = {r["text"] for r in rows}
    sources = [r for r in rows if r.get("label") == "true" and _facts(r)]
    rng.shuffle(sources)
    total = sum(mix.values())
    want = {lie: round(n * c / total) for lie, c in mix.items()}
    used, out = set(), []
    # the rarer lies first: fewer rows can carry them
    for lie in sorted(want, key=lambda k: want[k]):
        made = 0
        for r in sources:
            if made >= want[lie]:
                break
            if r["id"] in used:
                continue
            facts = _facts(r)
            order = list(range(len(facts)))
            rng.shuffle(order)
            for i in order:
                cands = [c for c in candidates(r, facts[i], lie, tl, aliases, name_pool, rng) if c[0] not in texts]
                if cands:
                    new_text, new_val = cands[0]
                    form = [dict(f) for f in facts]
                    form[i] = dict(form[i], value=new_val)
                    out.append({"id": f"{r['id']}~{lie}", "text": new_text, "date": r["date"], "label": "false",
                                "form": json.dumps(form, ensure_ascii=False), "source": r["id"], "lie": lie, "kind": new_val["kind"]})
                    used.add(r["id"])
                    texts.add(new_text)
                    made += 1
                    break
    return out


if __name__ == "__main__":
    import sys
    from collections import Counter
    from common import load

    rows, lex = load()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 277
    synth = augment(rows, lex, n)
    print(f"{len(synth)} synthetic lies from {len(rows)} rows: {dict(Counter(s['lie'] for s in synth))}")
    print("by kind:", dict(Counter(s["kind"] for s in synth)))
    by_id = {r["id"]: r for r in rows}
    for s in random.Random(1).sample(synth, min(12, len(synth))):
        print(f"[{s['lie']}] {by_id[s['source']]['text']}\n    -> {s['text']}")
