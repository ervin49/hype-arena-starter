"""The temporal knowledge base and the fact checker.

build_kb(practice_rows, lexicon) -> KB
check_fact(fact, at_date, kb, exclude_row_ids=()) -> dict

The base keeps every observation of a fact, indexed by (subject, attribute):
- a row labelled true observes each of its facts (positive evidence);
- a row labelled false with one fact observes that value as false on its
  date (negative evidence); a false row with several facts proves only that
  one of them is false, so it counts only once the others are supported;
- rows labelled unsure observe nothing; they are kept for analysis.

Between two observations the value is unknown: a check on a date between
two equal observations is strong, between two different ones is weaker, and
past the last observation it weakens with the gap. Nothing is propagated
silently: every result says which case it is in ("case") and which rows
it rests on ("evidence_ids").
"""

import json
from collections import defaultdict
from datetime import date as _date

from arena.values import compatible, satisfies, values_equal

# Heuristic confidences per case, before calibration (eval/ can fit them).
CASE_CONFIDENCE = {
    "same_day_match": 0.95,
    "same_day_mismatch": 0.9,
    "between_equal_match": 0.95,
    "between_equal_mismatch": 0.92,
    "between_change_match_before": 0.85,
    "between_change_match_after": 0.6,
    "between_change_mismatch": 0.75,
    "after_last_match": 0.9,
    "after_last_mismatch": 0.8,
    "before_first_match": 0.85,
    "before_first_mismatch": 0.7,
    "negative_match": 0.85,
    "constraint_satisfied": 0.8,
    "constraint_violated": 0.85,
    "stable_match": 0.95,
    "stable_mismatch": 0.9,
}


def _days(iso):
    """Day number of a partial ISO date (its first day)."""
    parts = [int(p) for p in iso.split("-")]
    while len(parts) < 3:
        parts.append(1)
    return _date(*parts).toordinal()


class KB:
    def __init__(self, lexicon):
        self.lexicon = lexicon
        self.pos = defaultdict(list)    # key -> [obs]
        self.neg = defaultdict(list)
        self.unsure = defaultdict(list)
        self.row_facts = {}             # row id -> [fact]
        self.unl = defaultdict(list)    # key -> [obs] stated by any row, label unknown

    def add_statements(self, rows, extractions):
        """Facts rows state, whatever their label: corroboration, not proof.

        A row's statement never counts for a row of its own date (its page),
        so it cannot confirm itself; copies on one page count once."""
        for r, ex in zip(rows, extractions):
            for f in ex.get("facts") or []:
                key = (_canon_subject(f["subject"], self.lexicon), f["attribute"])
                self.unl[key].append({"row": r["id"], "date": r["date"],
                                      "day": _days(r["date"]), "value": f["value"]})
        for lst in self.unl.values():
            lst.sort(key=lambda o: o["day"])

    def keys(self):
        return set(self.pos) | set(self.neg)

    def observations(self, subject, attribute, exclude_row_ids=()):
        ex = set(exclude_row_ids)
        return ([o for o in self.pos.get((subject, attribute), []) if o["row"] not in ex],
                [o for o in self.neg.get((subject, attribute), []) if o["row"] not in ex])

    def value_at(self, subject, attribute, at_date, exclude_row_ids=()):
        """The value the evidence gives the fact on a date, or None.

        Used for generation-side questions (compare on 29 Oct): the latest
        exact positive observation on or before the date, when it is not
        contradicted by a later observation on or before the date."""
        pos, _ = self.observations(subject, attribute, exclude_row_ids)
        d = _days(at_date)
        exact = [o for o in pos if not o["value"].get("op") and o["day"] <= d]
        if not exact:
            return None
        last_day = max(o["day"] for o in exact)
        vals = [o["value"] for o in exact if o["day"] == last_day]
        if all(values_equal(vals[0], v) for v in vals[1:]):
            return vals[0]
        return None


def _canon_subject(subject, lexicon):
    if lexicon is None:
        return subject
    names = {s["name"] for s in lexicon.get("subjects", [])}
    if subject in names:
        return subject
    low = subject.lower()
    for s in lexicon.get("subjects", []):
        if low == s["name"].lower() or low in (a.lower() for a in s.get("aliases", [])):
            return s["name"]
    return subject


def _facts_of(row):
    form = row.get("form")
    if not form:
        return []
    facts = json.loads(form) if isinstance(form, str) else form
    return facts if isinstance(facts, list) else [facts]


def build_kb(practice_rows, lexicon):
    kb = KB(lexicon)
    pending_false = []
    for r in practice_rows:
        label = (r.get("label") or "").strip().lower()
        facts = _facts_of(r)
        if not facts or label not in ("true", "false", "unsure"):
            continue
        facts = [dict(f, subject=_canon_subject(f["subject"], lexicon)) for f in facts]
        kb.row_facts[r["id"]] = facts
        for f in facts:
            obs = {"row": r["id"], "date": r["date"], "day": _days(r["date"]),
                   "value": f["value"], "n_facts": len(facts)}
            key = (f["subject"], f["attribute"])
            if label == "true":
                kb.pos[key].append(obs)
            elif label == "unsure":
                kb.unsure[key].append(obs)
            elif len(facts) == 1:
                kb.neg[key].append(obs)
        if label == "false" and len(facts) > 1:
            pending_false.append((r, facts))
    for lst in list(kb.pos.values()) + list(kb.neg.values()) + list(kb.unsure.values()):
        lst.sort(key=lambda o: o["day"])
    # A false row with several facts: if all but one are supported by other
    # rows, the remaining one is the false one.
    for r, facts in pending_false:
        unsupported = [f for f in facts
                       if _check(f, r["date"], kb, (r["id"],))["status"] != "supported"]
        if len(unsupported) == 1:
            f = unsupported[0]
            key = (f["subject"], f["attribute"])
            kb.neg[key].append({"row": r["id"], "date": r["date"], "day": _days(r["date"]),
                                "value": f["value"], "n_facts": len(facts)})
            kb.neg[key].sort(key=lambda o: o["day"])
    return kb


def _result(status, case, evidence, reason):
    conf = CASE_CONFIDENCE.get(case) if status != "unknown" else None
    return {"status": status, "confidence": conf,
            "evidence_ids": [o["row"] for o in evidence][:10], "reason": reason, "case": case}


def _matches(claim, obs_value):
    """True if obs states the claim's value, False if it states another
    value of the claim's kind, None if they do not bear on each other."""
    if obs_value.get("kind") != claim.get("kind"):
        return None
    c_op, o_op = claim.get("op"), obs_value.get("op")
    if not c_op and not o_op:
        if values_equal(claim, obs_value):
            return True
        if compatible(claim, obs_value):
            return None   # dates of different precision that agree
        return False
    if not c_op and o_op:
        s = satisfies(claim, obs_value)
        return None if s else (False if s is False else None)
    if c_op and not o_op:
        return satisfies(obs_value, claim)
    return None


def _group(obs):
    """The observations on the nearest single day of a list sorted by day."""
    if not obs:
        return []
    return [o for o in obs if o["day"] == obs[0]["day"]]


def _check(fact, at_date, kb, exclude_row_ids=()):
    subject = _canon_subject(fact["subject"], kb.lexicon)
    attribute, claim = fact["attribute"], fact["value"]
    pos, neg = kb.observations(subject, attribute, exclude_row_ids)
    if not pos and not neg:
        return _result("unknown", "no_evidence", [], f"No evidence for {subject} {attribute}.")
    d = _days(at_date)

    # A value the dataset calls false near this date.
    for o in neg:
        if _matches(claim, o["value"]) is True and abs(o["day"] - d) <= 45:
            same_pos = [p for p in pos if p["day"] == d and _matches(claim, p["value"]) is True]
            if not same_pos:
                return _result("contradicted", "negative_match", [o],
                               f"{subject} {attribute}: the value is stated false on {o['date']}.")

    if not pos:
        return _result("unknown", "only_negative", neg[:3],
                       f"{subject} {attribute}: only false statements of other values.")

    exact = [o for o in pos if not o["value"].get("op")]
    distinct = []
    for o in exact:
        if not any(values_equal(o["value"], v) or compatible(o["value"], v) for v in distinct):
            distinct.append(o["value"])
    stable = len(exact) >= 2 and len(distinct) == 1
    # Facts of a date kind (founded, joined, an event's date) do not change.
    if exact and claim.get("kind") == "date" and len(distinct) == 1:
        stable = True

    if stable and not claim.get("op"):
        m = _matches(claim, exact[0]["value"])
        if m is True:
            return _result("supported", "stable_match", exact[:5],
                           f"{subject} {attribute} has always been stated as this value.")
        if m is False:
            return _result("contradicted", "stable_mismatch", exact[:5],
                           f"{subject} {attribute} is always stated as another value.")

    same = [o for o in pos if o["day"] == d]
    before = _group(sorted([o for o in pos if o["day"] < d], key=lambda o: -o["day"]))
    after = _group([o for o in pos if o["day"] > d])

    def verdict(group):
        ms = [_matches(claim, o["value"]) for o in group]
        if any(m is True for m in ms):
            return True
        if ms and all(m is False for m in ms):
            return False
        return None

    if same:
        v = verdict(same)
        if v is True:
            return _result("supported", "same_day_match", same,
                           f"{subject} {attribute}: same-day evidence states this value.")
        if v is False:
            return _result("contradicted", "same_day_mismatch", same,
                           f"{subject} {attribute}: same-day evidence states another value.")

    vb, va = verdict(before), verdict(after)
    if before and after:
        both_same = all(_matches(o["value"], before[0]["value"]) is True for o in after) \
            if not before[0]["value"].get("op") else False
        if vb is True and va is True:
            return _result("supported", "between_equal_match", before + after,
                           f"{subject} {attribute}: stated so on {before[0]['date']} and {after[0]['date']}.")
        if vb is False and va is False:
            case = "between_equal_mismatch" if both_same else "between_change_mismatch"
            return _result("contradicted", case, before + after,
                           f"{subject} {attribute}: {before[0]['date']} and {after[0]['date']} state other values.")
        if vb is True and va is False:
            return _result("supported", "between_change_match_before", before + after,
                           f"{subject} {attribute}: stated so on {before[0]['date']}, changed by {after[0]['date']}.")
        if vb is False and va is True:
            return _result("supported", "between_change_match_after", after + before,
                           f"{subject} {attribute}: another value on {before[0]['date']}, this one by {after[0]['date']}.")
    if before and not after:
        if vb is True:
            return _result("supported", "after_last_match", before,
                           f"{subject} {attribute}: last stated so on {before[0]['date']}.")
        if vb is False:
            return _result("contradicted", "after_last_mismatch", before,
                           f"{subject} {attribute}: last stated as another value on {before[0]['date']}.")
    if after and not before:
        if va is True:
            return _result("supported", "before_first_match", after,
                           f"{subject} {attribute}: first stated so on {after[0]['date']}.")
        if va is False:
            return _result("contradicted", "before_first_mismatch", after,
                           f"{subject} {attribute}: first stated as another value on {after[0]['date']}.")
    # Constraints (op) on either side, or dates of a different precision.
    near = sorted(pos, key=lambda o: abs(o["day"] - d))[:3]
    ms = [_matches(claim, o["value"]) for o in near]
    if ms and ms[0] is True:
        return _result("supported", "constraint_satisfied", near[:1],
                       f"{subject} {attribute}: consistent with {near[0]['date']}.")
    if ms and ms[0] is False:
        return _result("contradicted", "constraint_violated", near[:1],
                       f"{subject} {attribute}: inconsistent with {near[0]['date']}.")
    return _result("unknown", "undecided", near,
                   f"{subject} {attribute}: the evidence does not decide this value.")


def _num(v):
    from arena.values import canonical_amount
    c = canonical_amount(v)
    return c[1] if c else None


def _bin_days(n):
    if n is None:
        return "none"
    for b in (0, 7, 30, 90, 180):
        if n <= b:
            return str(b)
    return "more"


def fact_features(fact, at_date, kb, exclude_row_ids=()):
    """What the evidence says about a fact, as features for arena.ml."""
    subject = _canon_subject(fact["subject"], kb.lexicon)
    claim = fact["value"]
    pos, neg = kb.observations(subject, fact["attribute"], exclude_row_ids)
    d = _days(at_date)
    m_pos = [(o, _matches(claim, o["value"])) for o in pos]
    m_neg = [(o, _matches(claim, o["value"])) for o in neg]
    f = {"kind": claim.get("kind"), "has_op": bool(claim.get("op")),
         "n_pos": min(len(pos), 10), "n_neg": min(len(neg), 5)}
    f["seen_pos"] = any(m is True for _, m in m_pos)
    f["seen_pos_before"] = any(m is True and o["day"] < d for o, m in m_pos)
    f["seen_pos_after"] = any(m is True and o["day"] > d for o, m in m_pos)
    f["seen_pos_same_day"] = any(m is True and o["day"] == d for o, m in m_pos)
    f["other_same_day"] = any(m is False and o["day"] == d for o, m in m_pos)
    f["seen_neg"] = any(m is True for _, m in m_neg)
    f["seen_neg_near"] = any(m is True and abs(o["day"] - d) <= 30 for o, m in m_neg)
    before = [o for o in pos if o["day"] < d]
    after = [o for o in pos if o["day"] > d]
    f["gap_before"] = _bin_days(d - before[-1]["day"] if before else None)
    f["gap_after"] = _bin_days(after[0]["day"] - d if after else None)
    distinct = []
    for o in pos:
        if not any(values_equal(o["value"], v) for v in distinct):
            distinct.append(o["value"])
    f["n_distinct"] = min(len(distinct), 4)
    c = _num(claim) if not claim.get("op") else None
    trend = "na"
    if c is not None and before:
        b = _num(before[-1]["value"])
        prior = [o for o in before if not values_equal(o["value"], before[-1]["value"])]
        if b is not None:
            if abs(c - b) <= 1e-9 * max(1, abs(b)):
                trend = "equal"
            else:
                rel = abs(c - b) / max(abs(b), 1e-9)
                f["rel_diff"] = "small" if rel < 0.1 else "mid" if rel < 0.5 else "large"
                p = _num(prior[-1]["value"]) if prior else None
                if p is None or p == b:
                    trend = "up" if c > b else "down"
                else:
                    trend = "with" if (c - b) * (b - p) > 0 else "against"
            if after:
                a = _num(after[0]["value"])
                if a is not None and a != b:
                    lo, hi = min(a, b), max(a, b)
                    trend += "_between" if lo <= c <= hi else "_outside"
    f["trend"] = trend
    # corroboration: other pages within 60 days, any label
    same_days, diff_days = set(), set()
    for o in kb.unl.get((subject, fact["attribute"]), []):
        if o["day"] == d or abs(o["day"] - d) > 60 or o["row"] in exclude_row_ids:
            continue
        m = _matches(claim, o["value"])
        if m is True:
            same_days.add(o["day"])
        elif m is False:
            diff_days.add(o["day"])
    n = len(same_days) + len(diff_days)
    f["u_any"] = n > 0
    f["u_same"] = bool(same_days)
    f["u_diff"] = bool(diff_days)
    if n:
        share = len(same_days) / n
        f["u_share"] = "0" if share == 0 else "low" if share < 0.34 else "mid" if share < 0.67 else "high"
    return f


def check_fact(fact, at_date, kb, exclude_row_ids=()):
    res = _check(fact, at_date, kb, exclude_row_ids)
    res["features"] = fact_features(fact, at_date, kb, exclude_row_ids)
    return res
