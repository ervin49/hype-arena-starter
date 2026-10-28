"""Rule audit on the practice data with the gold forms: what each evidence situation is worth.

Oracle forms, other pages only. Reproduces the tables of PLAN_ENGINE.md section 1; re-run
after every engine change. `--dates` lists the true one-time-date rows that mismatch (the
regression set for plans versus realised dates).

    .venv/bin/python scripts/rule_audit.py
    .venv/bin/python scripts/rule_audit.py --dates
"""
import collections, csv, json, re, sys
from datetime import date
sys.path.insert(0, ".")
from arena.values import canonical_amount, values_equal

MOVING = re.compile(r"^(latest|last|next|current|newest|planned|target)_|_since$")
rows = list(csv.DictReader(open("data/practice.csv", encoding="utf-8")))

def day(s):
    p = [int(x) for x in s.split("-")]
    while len(p) < 3:
        p.append(1)
    return date(*p).toordinal()

def num(v):
    c = canonical_amount(v)
    return c[1] if c else None

page, pid, prev = {}, -1, None
for r in rows:
    if r["date"] != prev:
        pid, prev = pid + 1, r["date"]
    page[r["id"]] = pid
obs = collections.defaultdict(list)
for r in rows:
    for x in json.loads(r["form"]):
        obs[(x["subject"], x["attribute"])].append((day(r["date"]), r["label"], x["value"], r["id"], page[r["id"]]))

def show(title, C):
    print("\n" + title)
    cats = sorted({k for k, _ in C}, key=lambda k: -sum(C[(k, l)] for l in ("true", "false", "unsure")))
    for k in cats:
        t, f, u = C[(k, "true")], C[(k, "false")], C[(k, "unsure")]
        n = t + f + u
        print(f"  {k:45} n={n:4}  true={t / n:5.1%}  false={f / n:5.1%}  unsure={u / n:5.1%}")

if "--dates" in sys.argv:
    for r in rows:
        for x in json.loads(r["form"]):
            v = x["value"]
            if v["kind"] != "date" or MOVING.search(x["attribute"]) or r["label"] != "true":
                continue
            trues = [o for o in obs[(x["subject"], x["attribute"])] if o[4] != page[r["id"]] and o[1] == "true"]
            if trues and not any(v["value"][:min(len(v["value"]), len(o[2]["value"]))] == o[2]["value"][:min(len(v["value"]), len(o[2]["value"]))] for o in trues):
                print(r["id"], r["date"], x["subject"], x["attribute"], v["value"], "|", r["text"][:70])
    sys.exit()

M1, M2, M3, LIES = collections.Counter(), collections.Counter(), collections.Counter(), collections.Counter()
for r in rows:
    d, lab = day(r["date"]), r["label"]
    facts = json.loads(r["form"])
    for x in facts:
        v = x["value"]
        if v.get("op"):
            continue
        c = num(v)
        others = [o for o in obs[(x["subject"], x["attribute"])] if o[4] != page[r["id"]]]
        trues = [o for o in others if o[1] == "true" and not o[2].get("op")]
        before = [o for o in trues if o[0] < d]
        after = [o for o in trues if o[0] > d]
        b = max(before, key=lambda o: o[0]) if before else None
        a = min(after, key=lambda o: o[0]) if after else None
        eqb, eqa = b and values_equal(v, b[2]), a and values_equal(v, a[2])
        if b and a:
            if eqb and eqa:
                cat = "both_match"
            elif eqb:
                cat = "match_before_only"
            elif eqa:
                cat = "match_after_only"
            else:
                nb, na = num(b[2]), num(a[2])
                cat = "between_two_different" if None not in (c, nb, na) and nb != na and min(nb, na) < c < max(nb, na) else "neither_matches"
        elif b:
            cat = "after_last:" + ("match" if eqb else "mismatch")
        elif a:
            cat = "before_first:" + ("match" if eqa else "mismatch")
        else:
            cat = "no_true_evidence"
        M1[(cat, lab)] += 1
        if len(trues) >= 2:
            distinct = []
            for o in trues:
                if not any(values_equal(o[2], u) for u in distinct):
                    distinct.append(o[2])
            if len(distinct) == 1 and not values_equal(v, distinct[0]):
                lo, hi = min(o[0] for o in trues), max(o[0] for o in trues)
                M2[("inside_span" if lo <= d <= hi else "outside_span", lab)] += 1
        near = [o for o in others if abs(o[0] - d) <= 45]
        same = len({o[4] for o in near if values_equal(v, o[2])})
        diff = len({o[4] for o in near if not values_equal(v, o[2]) and o[2].get("kind") == v.get("kind") and not o[2].get("op")})
        k = ("no_nearby_source" if same + diff == 0 else f"all_agree(n={min(same, 3)}{'+' if same >= 3 else ''})" if diff == 0
             else f"all_disagree(n={min(diff, 3)})" if same == 0 else "mixed")
        M3[(k, lab)] += 1
        if lab == "false" and len(facts) == 1:
            if not trues:
                LIES["no other true evidence"] += 1
            elif any(values_equal(v, o[2]) for o in trues):
                ds = [o[0] for o in trues if values_equal(v, o[2])]
                LIES["stale: true " + ("earlier" if max(ds) < d else "later" if min(ds) > d else "both sides")] += 1
            else:
                fam = [num(o[2]) for o in trues if num(o[2]) is not None]
                LIES["fabricated name/date/bool" if c is None or not fam else
                     "fabricated number " + ("above max" if c > max(fam) else "below min" if c < min(fam) else "inside range")] += 1

show("M1  value vs nearest true observation before/after", M1)
show("M2  '>=2 equal true observations of another value' (stable_mismatch trigger)", M2)
show("M3  consensus of independent nearby sources, any label", M3)
print("\nLies (single-fact false rows):")
for k, n in LIES.most_common():
    print(f"  {n:4}  {k}")
