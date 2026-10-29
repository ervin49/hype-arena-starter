"""New claims from the practice evidence: candidates, then the best 1,000 that validate.

generate_candidates(practice_rows, lexicon, as_of) -> [claim]
select_claims(practice_rows, lexicon, as_of, input_texts, n) -> ([claim], report)

Evidence is read from practice rows labelled true (values without op). Each
(subject, attribute) gets a timeline of segments: runs of equal values, in date
order. Candidates only use what the timeline shows:

- change:   two values, the first's segment wholly before the second's;
- at_event: an event's date reported after it took place, inside one segment;
- compare:  dates reported after they passed, or amounts stable up to the as-of date;
- fact:     a value stable up to the as-of date, or a date reported after it passed;
- relation: a link naming a lexicon entity, and that entity's fact while the link held.

A candidate carries several wordings; the first that validates is kept.
Confidences are heuristics from the evidence, not calibrated probabilities.
"""
import json
import os
import re
from collections import Counter, defaultdict
from datetime import date

from arena.render import render_value
from arena.validate import Validator, attribute_words
from arena.values import canonical_amount, comparable, compatible, date_interval, norm_name, values_equal

CALIBRATION = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "reports", "claims_calibration.json")
MIN_GROUP_PRECISION = 0.98   # a group must be this right at every backtest cut-off to be kept
UNMEASURED_CONFIDENCE = 0.8  # a group the backtest cannot judge (relation): kept, never trusted high
MAX_CLAIMS_PER_FACT = 10  # x3 in the second pass; the kept groups' candidates fill the 1,000 with room
MAX_CLAIMS_PER_EVENT = 60  # at_event values can't be checked on unseen rows: capped at 0.95, kept to a share
MAX_DATE_COMPARES_PER_FACT = 40  # second pass: date compares measure 133/133 on unseen rows
# Attributes whose words a strict referee may read as a comparison or a time word of the
# sentence itself ("maximum seats", "uptime last quarter"): no claim is built on them.
RISKY_ATTRIBUTE = re.compile(r"^(max|min|minimum|maximum)_|_last_(quarter|month|year)$")
ACRONYMS = {"ceo": "CEO", "cto": "CTO", "sla": "SLA", "cli": "CLI", "eu": "EU", "soc2": "SOC 2",
            "sdk": "SDK", "ide": "IDE", "ai": "AI", "nps": "NPS", "arr": "ARR", "api": "API",
            "ides": "IDEs", "sdks": "SDKs"}
# Dates that move by nature, even after they pass: a pointer to the latest or next one, a plan,
# a target, or a role that changes hands. `latest_release_date` moved from 20 June to 5 October
# in the practice data, which made a date compare false a month later. Only one-time events
# (founded, joined, launched, released...) stay true once they have happened.
MOVING_DATE = re.compile(r"^(latest|last|next|current|newest|planned|target)_|_since$|^(training_data_cutoff|lease_end|net_zero_date)$")
DATE_NOUNS = {"date": "", "launched": "launch", "joined": "start", "founded": "founding",
              "released": "release", "opened": "opening", "beta_opened": "beta opening",
              "stable_release": "stable release", "lease_end": "lease end"}


def words(attribute):
    return " ".join(ACRONYMS.get(w, w) for w in attribute_words(attribute).split())


def days(iso):
    return date.fromisoformat(iso).toordinal()


class Segment:
    def __init__(self, value, d, rid):
        self.value, self.first, self.last, self.rows, self.n = value, d, d, [rid], 1

    def add(self, value, d, rid):
        if value["kind"] == "date" and len(value["value"]) > len(self.value["value"]):
            self.value = value  # keep the most precise of compatible dates
        self.last, self.n = d, self.n + 1
        self.rows.append(rid)


class Evidence:
    def __init__(self, practice_rows, lexicon, as_of):
        self.as_of = as_of
        self.lexicon = lexicon
        self.events = list(lexicon.get("events", []))
        self.attributes = {s["name"]: set(s["attributes"]) for s in lexicon["subjects"]}
        names = {}
        for s in lexicon["subjects"]:
            for n in [s["name"]] + list(s.get("aliases", [])):
                names[norm_name(n)] = s["name"]
        self.entity = names
        obs, self.neg = defaultdict(list), defaultdict(list)
        for r in practice_rows:
            if not r.get("form"):
                continue
            facts = json.loads(r["form"])
            for f in facts:
                key = (f["subject"], f["attribute"])
                if key[0] not in self.attributes or key[1] not in self.attributes[key[0]] or "op" in f["value"]:
                    continue
                if RISKY_ATTRIBUTE.search(key[1]):
                    continue
                if r["label"] == "true":
                    obs[key].append((r["date"], f["value"], r["id"]))
                elif r["label"] == "false" and len(facts) == 1:
                    self.neg[key].append((r["date"], f["value"], r["id"]))
        self.timelines = {k: self._segments(sorted(v, key=lambda o: (o[0], o[2]))) for k, v in obs.items()}
        self.obs = obs

    @staticmethod
    def _segments(observations):
        segs = []
        for d, v, rid in observations:
            if segs and compatible(segs[-1].value, v):
                segs[-1].add(v, d, rid)
            else:
                segs.append(Segment(v, d, rid))
        return segs

    def refuted(self, key, value, since):
        """A row labelled false states this value on or after `since`."""
        return any(d >= since and values_equal(v, value) for d, v, _ in self.neg.get(key, []))

    # -- the value of a fact on the as-of date ----------------------------------
    def past_date(self, key):
        """A one-time date reported after it passed, all such reports agreeing: (value, confidence, rows)."""
        if MOVING_DATE.search(key[1]):
            return None
        reports = [(d, v, rid) for d, v, rid in self.obs.get(key, []) if v["kind"] == "date"
                   and d >= date_interval(v["value"])[1]]
        if not reports:
            return None
        best = max((v for _, v, _ in reports), key=lambda v: len(v["value"]))
        if not all(compatible(best, v) for _, v, _ in reports):
            return None
        if self.refuted(key, best, "0000"):
            return None
        conf = 0.97 if len(reports) >= 2 else 0.93
        return best, conf, [rid for _, _, rid in reports][:5]

    def at_as_of(self, key):
        """The value on the as-of date, if the evidence makes it safe: (value, confidence, rows)."""
        segs = self.timelines.get(key)
        if not segs:
            return None
        if segs[-1].value["kind"] == "date":
            return self.past_date(key)
        last = segs[-1]
        gap = days(self.as_of) - days(last.last)
        if self.refuted(key, last.value, last.first):
            return None
        if len(segs) == 1 and last.n >= 3:
            conf = 0.93 if gap <= 120 else 0.88
        elif last.n >= 2 and gap <= 60:
            conf = 0.88
        elif len(segs) == 1 and last.n == 2:
            conf = 0.85
        else:
            return None
        return last.value, conf, last.rows[-5:]

    def event_dates(self):
        out = {}
        for e in self.events:
            got = self.past_date((e, "date"))
            if got and len(got[0]["value"]) == 10:
                out[e] = got
        return out


def _claim(t, group, form, texts, score, rows, facts):
    """score: the evidence heuristic, used to rank claims inside a group.
    confidence: set from the group's backtest (reports/claims_calibration.json) in select_claims."""
    return {"id": None, "type": t, "group": group, "texts": [x for x in texts if x], "form": form,
            "label": "true", "score": round(score, 3), "confidence": round(score, 3),
            "evidence_ids": list(dict.fromkeys(rows)), "facts": facts}


def _facts(ev, out):
    for key in ev.timelines:
        got = ev.at_as_of(key)
        if not got:
            continue
        value, conf, rows = got
        s, a = key
        w = words(a)
        if value["kind"] == "boolean":
            texts = [f"{s} — {w}: yes." if value["value"] else f"{s} — {w}: no."]
        else:
            v = render_value(value)
            if v is None:
                continue
            texts = [f"{s} — {w}: {v}.", f"{s}: {v}."]
        group = ("fact.date" if value["kind"] == "date" else
                 "fact.unchanged" if len(ev.timelines[key]) == 1 else "fact.changed")
        out.append(_claim("fact", group, {"subject": s, "attribute": a, "value": value}, texts, conf - 0.02, rows, [key]))


def _changes(ev, out):
    for key, segs in ev.timelines.items():
        kind = segs[0].value["kind"]
        if kind in ("date", "boolean"):
            continue
        s, a = key
        for i, x in enumerate(segs):
            for y in segs[i + 1:]:
                if compatible(x.value, y.value) or x.value["kind"] != y.value["kind"]:
                    continue
                if kind == "name":
                    nx, ny = norm_name(x.value["value"]), norm_name(y.value["value"])
                    if nx in ny or ny in nx:  # Nimbus / Nimbus Cloud: a spelling, not a change
                        continue
                elif not comparable(x.value, y.value):
                    continue
                fx, fy = render_value(x.value), render_value(y.value)
                if fx is None or fy is None:
                    continue
                conf = 0.95 if x.n >= 2 and y.n >= 2 else 0.88 if max(x.n, y.n) >= 2 else 0.8
                form = {"subject": s, "attribute": a, "from": x.value, "to": y.value}
                texts = [f"{s} {words(a)} went from {fx} to {fy}.", f"{s} went from {fx} to {fy}."]
                out.append(_claim("change", "change", form, texts, conf, x.rows[-2:] + y.rows[:2], [key]))


def possessive(name):
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def _had(attribute, rendered):
    """`38 employees` for `employees`, `341,000,000 monthly active users` for `monthly_active_users`:
    the count with the attribute's words before its noun (value-forms allows up to two), or None."""
    aw, vw = words(attribute).split(), rendered.split()
    if len(vw) != 2 or not vw[0][0].isdigit() or len(aw) > 3:
        return None
    noun, last = vw[1].lower(), aw[-1].lower()
    if last not in (noun, noun + "s", noun + "es", noun.rstrip("s")):
        return None
    return " ".join([vw[0]] + aw[:-1] + [ACRONYMS.get(noun, vw[1])])


def _at_events(ev, out):
    for event, (edate, econf, erows) in ev.event_dates().items():
        e = edate["value"]
        for key, segs in ev.timelines.items():
            s, a = key
            if s == event or segs[0].value["kind"] in ("date", "boolean"):
                continue
            for seg in segs:
                if not (seg.first <= e <= seg.last) or seg.n < 2:
                    continue
                if ev.refuted(key, seg.value, seg.first):
                    break
                before = max(d for d, v, _ in ev.obs[key] if d <= e and compatible(v, seg.value))
                after = min(d for d, v, _ in ev.obs[key] if d >= e and compatible(v, seg.value))
                span = days(after) - days(before)
                conf = 0.95 if span == 0 else 0.93 if span <= 60 else 0.88 if span <= 150 else 0.82
                v = render_value(seg.value)
                if v is None:
                    break
                form = {"subject": s, "attribute": a, "event": event, "value": seg.value}
                texts = [f"{s} {words(a)} was {v} at the time of {event}.",
                         f"{s} {words(a)} stood at {v} during {event}.",
                         f"{s} had {v} at the time of {event}."]
                had = _had(a, v)
                if had:  # "Hooly had 38 employees", not "Hooly employees was 38 employees"
                    texts.insert(0, f"{s} had {had} at the time of {event}.")
                out.append(_claim("at_event", "at_event", form, texts, min(conf, econf), seg.rows[:3] + erows[:1], [key, ("@event", event)]))
                break


def _date_phrase(subject, attribute):
    noun = DATE_NOUNS.get(attribute, words(attribute) if attribute.endswith("date") else f"{words(attribute)} date")
    return [f"{possessive(subject)} {noun}" if noun else subject, f"the {noun} of {subject}" if noun else subject]


def _compares(ev, out):
    current = {}
    for key in ev.timelines:
        got = ev.at_as_of(key)
        if got and got[0]["kind"] not in ("name", "boolean"):
            current[key] = got
    keys = sorted(current)
    for i, k1 in enumerate(keys):
        for k2 in keys[i + 1:]:
            (v1, c1, r1), (v2, c2, r2) = current[k1], current[k2]
            if v1["kind"] != v2["kind"]:
                continue
            if v1["kind"] == "date":
                a1, b1 = date_interval(v1["value"])
                a2, b2 = date_interval(v2["value"])
                if b1 < a2:
                    op = "lt"
                elif b2 < a1:
                    op = "gt"
                else:
                    continue  # same day, or overlapping precision: no safe order
                for (l, vl, cl, rl), (r, vr, cr, rr), o in (((k1, v1, c1, r1), (k2, v2, c2, r2), op),
                                                         ((k2, v2, c2, r2), (k1, v1, c1, r1), {"lt": "gt", "gt": "lt"}[op])):
                    phrase = "came before" if o == "lt" else "came after"
                    lefts, rights = _date_phrase(*l), _date_phrase(*r)
                    texts = [f"{lefts[0]} {phrase} {rights[0]}.", f"{lefts[1]} {phrase} {rights[1]}."]
                    form = {"left": {"subject": l[0], "attribute": l[1]},
                            "right": {"subject": r[0], "attribute": r[1]}, "op": o}
                    out.append(_claim("compare", "compare.date", form, texts, min(cl, cr) - 0.01, rl[:2] + rr[:2], [l, r]))
                    break  # one direction per pair; the other is the same claim mirrored
                continue
            if k1[1] != k2[1] or k1[0] == k2[0] or not comparable(v1, v2):
                continue
            if v1["kind"] == "version":
                p1, p2 = v1["value"].split("."), v2["value"].split(".")
                if len(p1) != len(p2):
                    continue
                m1, m2 = [int(x) for x in p1], [int(x) for x in p2]
            else:
                m1, m2 = canonical_amount(v1)[1], canonical_amount(v2)[1]
            op = "gt" if m1 > m2 else "lt" if m1 < m2 else "eq"
            w = words(k1[1])
            if v1["kind"] == "money":
                phrase = {"gt": "costs more than", "lt": "costs less than", "eq": "costs the same as"}[op]
                texts = [f"{k1[0]} {phrase} {k2[0]}."] if k1[1] == "price" else [f"{k1[0]} {phrase} {k2[0]} for {w}."]
            elif v1["kind"] == "duration":
                adj = {"gt": "a longer", "lt": "a shorter", "eq": "the same"}[op]
                texts = [f"{k1[0]} has {adj} {w} {'as' if op == 'eq' else 'than'} {k2[0]}."]
            else:
                adj = {"gt": "a higher", "lt": "a lower", "eq": "the same"}[op]
                texts = [f"{k1[0]} has {adj} {w} {'as' if op == 'eq' else 'than'} {k2[0]}.",
                         f"{k1[0]} ranks {'higher than' if op == 'gt' else 'lower than' if op == 'lt' else 'equal to'} {k2[0]}."]
            form = {"left": {"subject": k1[0], "attribute": k1[1]},
                    "right": {"subject": k2[0], "attribute": k2[1]}, "op": op}
            conf = min(c1, c2) - (0.05 if op == "eq" else 0.03)
            out.append(_claim("compare", "compare.amount", form, texts, conf, r1[-2:] + r2[-2:], [k1, k2]))


def _relations(ev, out):
    for (s, link), segs in ev.timelines.items():
        if segs[0].value["kind"] != "name":
            continue
        for seg in segs:
            target = ev.entity.get(norm_name(seg.value["value"]))
            if not target or target == s:
                continue
            for (t, a), tsegs in ev.timelines.items():
                if t != target:
                    continue
                past = ev.past_date((t, a)) if tsegs[0].value["kind"] == "date" else None
                if past:  # a date that happened holds whenever the link held
                    value, conf, rows = past
                else:
                    hit = next((x for x in tsegs if x.first <= seg.last and x.last >= seg.first and x.n >= 2), None)
                    if not hit or len(tsegs) > 1:
                        continue
                    value, conf, rows = hit.value, 0.88, hit.rows[:3]
                if value["kind"] == "boolean":
                    continue
                v = render_value(value)
                if v is None:
                    continue
                form = {"subject": s, "link": link, "target": target, "attribute": a, "value": value}
                texts = [f"The {words(link)} of {s} — {words(a)}: {v}.",
                         f"{possessive(s)} {words(link)} — {words(a)}: {v}."]
                out.append(_claim("relation", "relation", form, texts, min(conf, 0.92), seg.rows[:2] + rows[:2], [(s, link), (t, a)]))


def generate_candidates(practice_rows, lexicon, as_of):
    ev = Evidence(practice_rows, lexicon, as_of)
    out = []
    for build in (_relations, _at_events, _changes, _facts, _compares):
        build(ev, out)
    return out


def load_calibration(path=CALIBRATION):
    """{group: {"keep": bool, "confidence": float}} from the backtest, or None without the file."""
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return {g["group"]: g for g in json.load(f)["groups"]}


def calibrate(candidates, calibration):
    """Drop the groups the backtest rejects; set each claim's confidence from its group."""
    if calibration is None:
        return candidates
    out = []
    for c in candidates:
        g = calibration.get(c["group"])
        if g is None or not g["keep"]:
            continue
        out.append({**c, "confidence": g["confidence"]})
    return out


def _known_names(lexicon):
    names = set(lexicon.get("events", []))
    for sub in lexicon["subjects"]:
        names.update([sub["name"]] + list(sub.get("aliases", [])))
    return {norm_name(n) for n in names if isinstance(n, str)}


def _names_outside(claim, known):
    """1 if a name value of the claim (value, from or to) is no lexicon subject, alias or event."""
    form = claim["form"]
    values = [form.get(k) for k in ("value", "from", "to")]
    return int(any(isinstance(v, dict) and v.get("kind") == "name" and norm_name(str(v.get("value"))) not in known
                   for v in values))


def select_claims(practice_rows, lexicon, as_of, input_texts, n=1000, calibration="default", check_rows=None):
    """The n best candidates whose text validates, each fact in at most a few claims.

    calibration: "default" reads reports/claims_calibration.json (as the image ships it),
    None keeps every group with its heuristic score (what the backtest measures), or a dict.
    check_rows: input rows the engine is confident are true, as practice rows (arena.controls).
    A candidate that does not survive with them added to the evidence is vetoed: chosen only
    when the others run out, at the lowest confidence (0.5). A group that loses a share v of
    its candidates this way is contradicted by the input more than the backtest saw, so its
    confidence becomes c * (1 - v), never below 0.5.
    """
    if calibration == "default":
        calibration = load_calibration()
    validator = Validator(practice_rows, lexicon, input_texts)
    raw = generate_candidates(practice_rows, lexicon, as_of)
    candidates = calibrate(raw, calibration)
    vetoed = set()
    if check_rows:
        survive = {json.dumps(c["form"], sort_keys=True)
                   for c in calibrate(generate_candidates(practice_rows + list(check_rows), lexicon, as_of), calibration)}
        vetoed = {json.dumps(c["form"], sort_keys=True) for c in candidates} - survive
    group_size, group_vetoed = Counter(c["group"] for c in candidates), Counter()
    for c in candidates:
        if json.dumps(c["form"], sort_keys=True) in vetoed:
            group_vetoed[c["group"]] += 1
    keep_share = {g: 1 - group_vetoed[g] / n_g for g, n_g in group_size.items()}
    # Highest confidence first; inside a confidence, the strongest evidence; types interleaved.
    known = _known_names(lexicon)
    by_type = defaultdict(list)
    for c in candidates:
        by_type[c["type"]].append(c)
    order = []
    for t, cs in by_type.items():
        # inside a confidence, a claim naming only lexicon entities first: a name the lexicon
        # lacks (a city, a person, a venue) is one the referee must match by its own words
        cs.sort(key=lambda c: (-c["confidence"], _names_outside(c, known), -c["score"]))
        order += [(-c["confidence"], i, t, c) for i, c in enumerate(cs)]
    order.sort(key=lambda x: x[:3])

    report = Counter(candidates=len(raw))
    for c in raw:
        report[f"candidates.{c['type']}"] += 1
    report["dropped_by_calibration"] = len(raw) - len(candidates)
    if check_rows:
        report["vetoed_by_input"] = len(vetoed)
        for g, k in group_vetoed.items():
            report[f"vetoed.{g}"] = k
    chosen, forms, texts, per_fact = [], set(), set(), Counter()
    passes = [(limit, False) for limit in (MAX_CLAIMS_PER_FACT, MAX_CLAIMS_PER_FACT * 3)]
    for limit, allow_vetoed in passes + ([(MAX_CLAIMS_PER_FACT * 3, True)] if vetoed else []):
        for _, _, t, c in order:
            if len(chosen) >= n:
                break
            key = json.dumps(c["form"], sort_keys=True)
            if key in vetoed and not allow_vetoed:
                continue
            cap = max(limit, MAX_DATE_COMPARES_PER_FACT) if c["group"] == "compare.date" and limit > MAX_CLAIMS_PER_FACT else limit
            if key in forms or any(per_fact[f] >= (MAX_CLAIMS_PER_EVENT if f[0] == "@event" else cap) for f in c["facts"]):
                continue
            for text in c["texts"]:
                claim = {k: v for k, v in c.items() if k not in ("texts", "facts", "score")}
                claim.update(id=f"gh-{len(chosen) + 1:04d}", text=text,
                             confidence=0.5 if key in vetoed else
                             round(max(0.5, c["confidence"] * keep_share[c["group"]]), 3))
                result = validator.validate(claim)
                if result["valid"] and text.lower() not in texts:
                    break
                report[f"rejected.{result['issues'][0].split(':')[0] if result['issues'] else 'duplicate text'}"] += 1
            else:
                continue
            chosen.append(claim)
            if key in vetoed:
                report["vetoed_but_needed"] += 1
            forms.add(key)
            texts.add(text.lower())
            for f in c["facts"]:
                per_fact[f] += 1
        if len(chosen) >= n:
            break
    for c in chosen:
        report[f"selected.{c['type']}"] += 1
    report["selected"] = len(chosen)
    return chosen, dict(sorted(report.items()))
