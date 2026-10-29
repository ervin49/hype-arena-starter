# Engine and claims plan, 29 Oct: three people, three prompts

The plan to the freeze after the organisers mapped the rubric. Who does what, on which branch, and the prompt each person gives their Claude session. No times: the team decides those. Everything was measured on `data/practice.csv` with the gold forms; `scripts/rule_audit.py` reproduces section 2's tables and must be re-run after every engine change.

## 1. Priorities, from the rubric

| Weight | Criterion | What it means tonight |
|---|---|---|
| **30%** | Correctness = **the 1,000 claims** | Every claim must survive an independent reading of the spec. **Top priority.** |
| **15%** | Self-evaluation = the 20k labels with their confidence | Remove the over-confident wrong answers (2.1 / 3.1) |
| 25% | Architecture | Diagram labels and the two missing boxes (later, C) |
| 20% | Demo | Video on the 09:00 sample, the Confidence page on screen (later) |
| 10% | Business | One paragraph in the video (later) |

**In tonight:** the claims work (section 4), the span fix and display confidences (3.1, 3.6), then plans versus realised dates (3.2) and the extraction guards (3.3), the `unsure` switch (3.5, default off), and the density test (section 5).
**Not tonight:** the count- and time-aware consensus features (3.4) and the timeline backend (section 8). Both are new core code whose gain can't be measured on practice.

## 2. What the data says (oracle forms, other pages only)

Honest numbers today:
- 87.0% out of fold, against 83.3% for "always true".
- 118 of 277 lies caught; ECE 0.027.
- On **new subjects 79.5%, below always-true (82.5%)**.

About 145 of our ~210 errors are rows where our evidence *contradicts* a true sentence.

### 2.1 The false-contradiction bug is a span bug

`arena/truth.py::_check` calls a fact "stable" when ≥ 2 true observations agree. It then returns `stable_mismatch` (contradicted, 0.9) for any other value **at any date**:

| `stable_mismatch` would fire | n | true | false |
|---|---|---|---|
| row date **inside** the span of the equal observations | 29 | 10% | **90%** |
| row date **outside** the span (before the first or after the last) | 101 | **74%** | 24% |

Inside the span the rule is excellent; outside it is wrong three times in four. To compensate, the trees learned to distrust *every* `stable_mismatch`. That's why "Hooly was founded in 2024", a labelled lie, gets `true 0.75`.

### 2.2 Dates: a plan is true when it is made

`_check` forces `stable = True` for any date fact with one distinct value. One-time dates with a mismatching observation are **50% true (n=20)**, because a planned date is true on the day it is planned:
- "set for 21 April" (Feb) is true, although the event was held on 28 April;
- "planned for 9 June" (April) is true, and so is "held on June 23" (July).

An observation is **realised** when its report day ≥ the end of the date it names. Only realised observations are stable evidence. A plan is checked against other plans, never against a later realised date.

### 2.3 A value against its nearest true neighbours

| Row's value vs nearest true observation before (b) / after (a) | n | true | false |
|---|---|---|---|
| matches both b and a | 579 | 94.6% | 5.4% |
| before the first, matches it | 357 | 92.7% | 3.9% |
| after the last, matches it | 325 | 93.5% | 4.3% |
| matches a only | 263 | 90.5% | 9.5% |
| matches b only | 226 | 85.8% | 13.3% |
| before the first, mismatch | 183 | 60.7% | 32.8% |
| after the last, mismatch | 152 | 56.6% | 41.4% |
| no true evidence | 133 | 88.7% | 5.3% |
| **matches neither b nor a** | 126 | 16.7% | **83.3%** |
| strictly between b < value < a | 20 | 95% | 5% |

- "Matches neither" is the strong contradiction.
- "Before first / after last mismatch" are coin flips and must not carry 0.7–0.8 confidence on their own.

### 2.4 What lies look like (202 single-fact lies with evidence)

| Kind | n |
|---|---|
| **stale**: true earlier | 60 |
| **stale**: true later | 36 |
| fabricated number above every true value (median ×1.29) | 48 |
| fabricated number below every true value | 22 |
| fabricated name / date / yes-no | 24 |
| fabricated number inside the range | 4 |

### 2.5 Consensus of nearby independent sources, labels ignored (±45 days)

| | n | true | false |
|---|---|---|---|
| all agree, 3+ sources | 195 | 95.9% | 4.1% |
| all agree, 1–2 | 677 | 94.7% | 4.6% |
| no nearby source | 609 | 82.3% | 11.5% |
| mixed | 544 | 84.4% | 15.6% |
| all disagree, 1 / 2 / 3 | 204 / 78 / 57 | 64.7 / 48.7 / 21.1% | 35.3 / 51.3 / **77.2%** |

The real input is about 10× denser than practice, so "no nearby source" will shrink and "3+" will grow.

### 2.6 `unsure` and small signals

- **`unsure`:** no page pins the fact's value on that date. Policy stays *never unsure* unless the organisers give a scoring rule.
- **Speakers:** rows starting `Gavin:` are 29% false (n=31), twice the base rate.
- **Approximations:** `about 2,600` keeps the exact value in the gold form, but `extract` drops it today.

## 3. Engine changes (A), in order, one commit each, each measured

### 3.1 `stable_mismatch` only inside the span: `arena/truth.py::_check`

`exact` is sorted by day.

```python
    if stable and not claim.get("op"):
        m = _matches(claim, exact[0]["value"])
        if m is True:
            return _result("supported", "stable_match", exact[:5], ...)
        if m is False and exact[0]["day"] <= d <= exact[-1]["day"]:
            return _result("contradicted", "stable_mismatch", exact[:5], ...)
        # outside the observed span: fall through to before_first / after_last below
```

What to expect:
- Most of the 151 true `stable_mismatch` rows move to `before_first_mismatch` / `after_last_mismatch`.
- What remains is ~90% false, so the trees can trust it again, and lies caught should rise.
- In the dense run nearly every fact will have two equal observations somewhere. Without this fix, every other value at any time becomes a 0.9 contradiction.

### 3.6 Display confidences: `arena/truth.py::CASE_CONFIDENCE` (right after 3.1)

- `before_first_mismatch` and `after_last_mismatch` → 0.55.
- `stable_mismatch` 0.9, now only inside the span.

The trees see the case names, not these numbers. So this is for the reasons on the page and the rules-only fallback. Retrain afterwards anyway.

### 3.2 Plans versus realised dates: `arena/truth.py::_check` (only after 3.1 is merged)

Delete `if exact and claim.get("kind") == "date" and len(distinct) == 1: stable = True`. Then, for date claims without `op`:

```python
from arena.values import date_interval
def realised(o):           # reported on or after the date it names
    return o["day"] >= _days(date_interval(o["value"]["value"])[1])
claim_is_plan = d < _days(date_interval(claim["value"])[0])
real = [o for o in exact if realised(o)]
if not claim_is_plan:
    # judged by realised observations only
    if real and all(compatible(real[0]["value"], o["value"]) for o in real):
        return supported "realised_match" / contradicted "realised_mismatch" (any row date)
    # several realised values (a moving date): before/after logic over `real` only
else:
    # a plan: only other plans near this date bear on it
    nearest plan within 90 days: match -> supported "plan_match" (0.85);
    mismatch -> contradicted "plan_mismatch" (0.6); none -> unknown "plan_unknown"
```

Add the new cases to `CASE_CONFIDENCE`.

Regression tests:
- The 10 rows from `scripts/rule_audit.py --dates` must not be contradicted: p-957, p-69, p-881, p-688, p-838, p-60, p-281, p-340, p-1027, p-1178.
- p-1347 ("founded 1 June 2024", a realised lie) must stay contradicted.

### 3.3 Extraction guards: `arena/extract.py`, `arena/classify.py` (one at a time)

1. **Fallback subject.** A fact whose subject is neither named nor in the page context (`subject_from == "other"`) is a guess.
   - Example: "…and has 7,777,777 users" was assigned to Hooly Photos and labelled `true 0.918`.
   - First try: drop it, add the issue `unplaced value`, and set `complete = False`.
   - If lies caught fall, keep the fact with check status `unknown` instead.
2. **Negated values.** "Hooly AI Pro does not cost €59 per month" → `true 0.946`.
   - `span["negated"]` is already set. Invert the check of a negated non-boolean fact (supported ↔ contradicted).
   - Add one minimal-pair test each way.
3. **Lost clauses.** Set `complete = False` when a parsed value (not approximate, not a range) was left unassigned because `none_score` won. 31 of 277 false rows lose a fact today.
4. **Approximations.** Keep the value, and keep `approx` as an issue feature.
5. **Speaker.** Add `issue=speaker` when the text matches `^[A-Z][a-z]+:`.

### 3.5 `unsure` switch: `arena/classify.py`, default off

`ARENA_UNSURE_WHEN_UNSEEN=1` exports `unsure` for a row when both hold:
- its weakest fact is `no_evidence`;
- no other source in the whole input states that fact.

Report the share of rows it touches on the density test (expect < 3%). It is turned on only if the organisers say an `unsure` scores better than a wrong answer. If `unsure` is neutral and wrong answers are penalised, also consider `ARENA_UNSURE_BELOW=0.6`.

## 4. Claims (B and C): make all 1,000 survive

1. **Independent referee (B).** In a **fresh session that never reads `arena/validate.py` or `arena/generate.py`**:
   - Re-implement the checks of `contracts/claim-forms.md`, `contracts/value-forms.md`, `contracts/entry.schema.json` and `contracts/claimed_value.schema.json` from the spec alone.
   - Run them over an `output.csv` and list every claim the referee rejects, with the rule and the sentence.
   - Also check the general rules:
     - no second value of the same kind in the sentence;
     - no month or time word outside the names;
     - a yes/no claim needs the attribute's words;
     - `Hooly` inside `Hooly AI Pro` names the plan only.

   C resolves every disagreement from the spec, then fixes the validator or drops/rewords the claims.
2. **Event dates (C).**
   - Print `Evidence.event_dates()` with the rows behind each date. Each anchor event needs ≥ 2 independent realised reports that agree.
   - If one rests on a single report, cap its claims at 40, so the selection fills from `change` and date compares.
   - Hand-read the rows behind each date.
3. **Mix toward the provably true (C).**
   - `change` is true by construction, date compares measured 127/127 on unseen rows, and `at_event` is capped at 0.95.
   - So: `MAX_CLAIMS_PER_EVENT` 100 → 60; a higher per-fact cap for date compares (today there's one `MAX_CLAIMS_PER_FACT` for all types); every `change` candidate.
   - Drop the 2 `at_event` claims on `open_roles`.
   - Re-run `scripts/backtest_claims.py`. Confidences stay as measured.
4. **Grammar (C).** Put `{s} had {v} at the time of {event}` first among the `at_event` templates. "services was 31 services" reads like a machine.
5. **Hand audit (all three).** Check 50 random claims against their evidence rows:
   - value rendering, plurals, currency period;
   - the event phrase;
   - the subject name exactly as the lexicon writes it.

## 5. Density test v2 (B): `scripts/synth_universe.py`

Today's synthetic 20k repeats sentences verbatim, so `source_key` collapses them, and the dense regime is never tested. Build it like this instead:
- Every practice row stays, with every fifth label hidden (as `scripts/input.py` does).
- Each row labelled **true** gets 9 copies:
  - new ids and the **same date**, label empty;
  - text varied so `source_key` differs: a prefix (`Note:`, `Update:`, `As announced,`), a suffix sentence (`That is the figure.`), or number formatting (`2,600` / `2600`);
  - **never** a changed value.
- Each row labelled **false** gets 1 copy. Unsure rows get none.
- Keep rows sorted by date so pages stay contiguous. That makes ≈ 16,000 rows.
- Run it with the runner (Docker limits, or `ARENA_DEADLINE`), then `scripts/check_output.py` against practice.

Report before and after each engine change:
- hidden-row accuracy and lies caught (these should **rise** with density, not fall);
- the control factors `k`;
- the false share on the input vs the control group;
- run time (under 10 min) and peak memory (under 2 GiB).

If accuracy falls with density, pseudo-labels are amplifying copied lies. Then cap pseudo observations per `(key, day)` at 1 and require two independent sources.

## 6. Harness and keep criteria (everyone)

```sh
.venv/bin/python -m pytest -q                       # must pass (398 today)
.venv/bin/python eval/train_model.py --no-save      # out of fold: 0.870, lies 118/277, ECE 0.027
.venv/bin/python scripts/shift_test.py              # random 88.8 | latest 83.5 | new subjects 79.5 (always true 82.5)
MINUTES=5 scripts/check.sh                          # 340/380 hidden (upper bound), 1,000 claims, exit 0
.venv/bin/python scripts/rule_audit.py              # section 2 tables, before/after
.venv/bin/python scripts/backtest_claims.py         # claims: strict precision per type
```

A local `output.csv` without Docker:

```sh
mkdir -p /tmp/arena/u /tmp/arena/o
python3 scripts/input.py data/practice.csv /tmp/arena/u/universe.csv && cp data/lexicon.json /tmp/arena/u/
ARENA_UNIVERSE=/tmp/arena/u ARENA_OUTPUT=/tmp/arena/o .venv/bin/python -m arena.runner
```

**Engine change kept only if** all of these hold:
- out of fold ≥ 0.870 **and** lies caught ≥ 118 (target 0.885 / 140);
- ECE ≤ 0.03;
- shift test not worse in any scenario (target: new subjects > 82.5%);
- tests and `check.sh` pass;
- density test not worse.

**Claims change kept only if** all of these hold:
- still exactly 1,000 valid claims;
- strict backtest precision not lower for any type;
- the referee finds no new disagreement.

**After a kept engine change, in this order:**
1. `eval/train_model.py`
2. `scripts/train_control.py`
3. `eval/train_ensemble.py`
4. `scripts/shift_test.py`
5. Commit the models, `eval/calibration_labels.json`, `reports/shift_test.json` and `reports/controls.json` with the code.

**Never** tune on the 09:00 sample, and never fit anything on `check.sh` numbers: the shipped model has seen those rows.

## 7. Who does what

| | Branch | Files | Work |
|---|---|---|---|
| **A** (engine) | `dev/a` | `arena/truth.py`, `extract.py`, `classify.py`, models | 3.1 → 3.6 → (C merges) → 3.2 → 3.3 → 3.5 |
| **B** (Ervin) | `dev/b` | new `scripts/referee.py`, `scripts/synth_universe.py` | Referee (4.1) first, then the density test (5); the hand audit (4.5) with everyone |
| **C** (platform) | `dev/c` | `arena/generate.py`, `validate.py`, `runner.py`, `controls.py`, `api/`, `frontend/`, STATUS.md | Claims (4.2–4.4), resolve the referee's findings, merges, density runs of every kept change, `train_control.py` after the last engine change, freeze |

Rules:
- **Own branch only.** Sync from `integration` at the start and before reporting. **C alone merges** into `integration` (`--no-ff`), after the checks in section 6.
- **Runtime:** pure Python with `jsonschema` only; no numeric libraries in the image. Keep `label_rows`'s signature.
- **Commits:** one change per commit, with its numbers in the message. No `Co-Authored-By` or "Generated with Claude" lines.
- **Docs:** don't edit README.md; STATUS.md is C's.
- **Freeze:** `integration` → `main`, `check.sh` from a fresh clone, PR "Git Happens" before 11:00. Nothing after.

## Prompt for A

```
I'm person A (engine/ML), team "Git Happens". Branch dev/a only; C merges.
Read PLAN_ENGINE.md sections 2, 3 and 6 first.

STEP 0: sync:
  git checkout dev/a && git status   # commit any WIP first
  git fetch origin && git merge origin/integration
  .venv/bin/python -m pytest -q && git push origin dev/a
  git rev-list --count dev/a..origin/integration   # must print 0

BASELINE: run scripts/rule_audit.py, eval/train_model.py --no-save, scripts/shift_test.py.
Save the numbers.

TASK, one commit per change, each measured (section 6) before the next starts:
1. 3.1: stable_mismatch only inside the span of the equal observations (arena/truth.py
   _check). Retrain, measure, report to C so it can be merged on its own.
2. 3.6: CASE_CONFIDENCE before_first_mismatch / after_last_mismatch -> 0.55.
3. 3.2: plans versus realised dates. Regression tests: the 10 rows of
   scripts/rule_audit.py --dates not contradicted; p-1347 stays contradicted.
4. 3.3: extraction guards, one at a time (fallback subject, negated values, lost clauses,
   approximations, speaker). Minimal-pair tests for each.
5. 3.5: ARENA_UNSURE_WHEN_UNSEEN switch, default OFF.
NOT tonight: 3.4 (consensus features) and the timeline backend.
Keep a change only if: out of fold >= 0.870 and lies >= 118/277, ECE <= 0.03, shift test
not worse in any scenario, tests and check.sh pass. Otherwise revert and note it as tried.
After a kept change: eval/train_model.py, scripts/train_control.py,
eval/train_ensemble.py, scripts/shift_test.py; commit the models and reports with the code.
Don't edit runner.py, io.py, generate.py, validate.py, controls.py, confidence.py, api/,
Dockerfile, README.md, STATUS.md. No Co-Authored-By lines.
BEFORE REPORTING: git fetch origin && git merge origin/integration && pytest && git push.
Report per change: commit, rule_audit M2 before -> after, out of fold, lies, ECE, shift
test, check.sh, tried and rejected.
```

## Prompt for B

```
I'm person B, team "Git Happens". Branch dev/b only; C merges.
Read PLAN_ENGINE.md sections 4, 5 and 6 first.

STEP 0: sync:
  git checkout dev/b && git status   # commit any WIP first
  git fetch origin && git merge origin/integration
  .venv/bin/python -m pytest -q && git push origin dev/b
  git rev-list --count dev/b..origin/integration   # must print 0

TASK 1: THE INDEPENDENT REFEREE (the most valuable task tonight; claims are 30%).
- Do NOT open arena/validate.py, arena/generate.py or tests/test_official_examples.py.
  Work from contracts/claim-forms.md, contracts/value-forms.md, contracts/*.schema.json and
  data/lexicon.json only. The point is a second, independent reading of the spec.
- Write scripts/referee.py: reads an output.csv, checks every claim row (type, text,
  form, label, confidence) against the spec, and prints each rejection with the rule and
  the sentence, plus a count per rule. Exit 0 if none.
- Also check: no second value of the same kind in the sentence; no month or time word
  outside the names; a yes/no claim needs the attribute's words; "Hooly" inside
  "Hooly AI Pro" names the plan only; the subject written exactly as in the lexicon.
- Test it on the official examples in the two .md files (they must all pass).
- Make an output.csv (PLAN_ENGINE.md section 6, "A local output.csv") and run it.
  Send C the full list of rejections. Don't change arena/ to fix them; C does.
TASK 2: DENSITY TEST v2, scripts/synth_universe.py (section 5). Run it on the current
engine and report: hidden-row accuracy, lies caught, control factors k, false share input
vs control, run time, peak memory. Then C re-runs it for every kept engine change.
TASK 3: the hand audit of 50 random claims with A and C (section 4.5).
Runtime stays pure Python. Don't edit arena/, api/, Dockerfile, README.md, STATUS.md.
No Co-Authored-By lines.
BEFORE REPORTING: git fetch origin && git merge origin/integration && pytest && git push.
Report: commit, the referee's rejections by rule, the density numbers.
```

## Prompt for C

```
I'm person C (platform), team "Git Happens". Branch dev/c; I merge into integration.
Read PLAN_ENGINE.md sections 4, 6 and 7 first.

STEP 0: sync dev/c with origin/integration; pytest.

TASK 1: CLAIMS (30% of the score), one change at a time, each with
scripts/backtest_claims.py and a run that still writes exactly 1,000 valid claims:
1. Event dates: print Evidence.event_dates() with the rows behind each date. Each anchor
   event needs >= 2 independent realised reports that agree; otherwise cap that event at
   40 claims. Hand-read the rows.
2. Mix: MAX_CLAIMS_PER_EVENT 100 -> 60, a higher per-fact cap for date compares (40),
   take every change candidate, drop the 2 at_event claims on open_roles.
3. Grammar: "{s} had {v} at the time of {event}" first among the at_event templates.
4. When B's referee reports: resolve every disagreement from the spec; fix validate.py
   (with a test) or drop/reword the claims it affects.
TASK 2: MERGES. A's 3.1 first, on its own. For every merge: tests, MINUTES=5
scripts/check.sh, the numbers not worse; then B's density test on the merged engine.
After the last engine change: scripts/train_control.py, scripts/shift_test.py.
TASK 3: STATUS.md after each merge; then the freeze checklist in PLAN_FINAL.md.
No Co-Authored-By lines.
```

## 8. Not tonight: the timeline backend (a record)

The idea is to rebuild each fact's step function from all 20,000 statements, then judge every row against the rebuilt value at its date:
- Fit an optimal piecewise-constant line per `(subject, attribute)` with a change penalty λ ≈ 1.5.
- Weights: labelled true +4, a labelled false −4, every other independent source +1.
- A row never confirms itself: it is excluded when recounting its run's support.

It is the only idea here whose value grows with the input's size, and it targets the stale-value lies (nearly half of them). It was dropped tonight because it is new core code, its gain can't be measured on practice, and a wrong λ would turn real changes into stale lies. If there is time after the freeze checklist, it belongs on `dev/timeline`, behind `ARENA_TRUTH=timeline`, with the old path as the fallback.
