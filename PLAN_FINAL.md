# Plan to the freeze: Git Happens

The last plan before the freeze. Who does what, on which branch, and the prompt each person gives their Claude session. No times: the team decides those.

## Where we are

**After the freeze nothing can be changed or inspected.** The organisers run our image once, offline, on ~20,000 rows: the 1,897 practice rows with their labels and ~18,000 unlabelled rows we never see. The 1,000 claims are judged against that whole universe. So every check has to be **inside the system** and run on its own.

| Part | State |
|---|---|
| Image (`Dockerfile`) | ✅ `scripts/check.sh` passes in Docker; our synthetic 20,000-row input runs in ~2 min of 30 |
| Labels, honest (models trained without the rows they're tested on) | 86.3% out of fold, against 83.3% for "always true"; hidden rows 337/380; lies caught 27/49 |
| Labels on **new subjects** (shift test) | **80.3%, worse than always "true" (82.5%)**: the main gap |
| Label confidence | Calibrated (ECE ~0.03). Run-time control: a held-out control group, which can only lower confidence |
| Claims | 1,000 valid: 294 date compares at 0.971, 700 change/at_event at 0.95 (capped), 6 others. Run-time veto from confident input rows |
| Claim confidence formula | The cautious Wilson bound. B's 0.99 (Laplace) was **not** taken: without a measurement of wording or the new data, the cautious number is the honest one |
| Tests | 178 Python tests; frontend type-checks |

Shift test (`scripts/shift_test.py`, current engine; models trained only on the "known" part):

| Unseen part | Right | Always "true" | ECE after control |
|---|---|---|---|
| Random pages | 88.0% | 83.9% | 0.048 |
| Latest pages | 83.7% | 81.5% | 0.032 |
| New subjects | **80.3%** | **82.5%** | 0.028 |

## What the organisers told us

1. The ~18,000 rows are **unlabelled**.
2. The 1,000 claims are **based on the 20,000** (see "Open questions").
3. Confidence may **overfit**: have **controls**.

## Rules everyone follows

- **Your own branch only:** A on `dev/a`, B on `dev/b`, C on `dev/c`. Start every session by bringing it up to date from `integration`:
  ```bash
  git checkout dev/X
  git fetch origin
  git merge origin/integration
  git push
  ```
- **C alone merges** `dev/*` into `integration` (`--no-ff`), and only after all checks pass: the tests, `MINUTES=5 scripts/check.sh` in Docker, and the numbers not getting worse.
- **`main`** is merged once, at the freeze. The pull request to QA-DNA comes from `main`.
- **Measure every change**, one change at a time, and report the numbers before and after. Changes that don't measure better are dropped.
- **Honest numbers only.** `check.sh`'s label count is an upper bound, because the shipped model has seen those rows. Use the out-of-fold numbers and the shift test.
- **No `Co-Authored-By` or "Generated with Claude" lines** in commits or PRs.
- **README.md:** don't edit it unless the team decides to. `STATUS.md` is C's.

## Who does what

### A: engine (`dev/a`): correctness on unseen rows

1. **New subjects:** with no evidence for a fact, lean `true` at around base-rate confidence, not a confident `false`. Target: new subjects above 82.5%.
2. **No facts read:** no confident answer.
3. **Lost clauses:** mark an extraction incomplete when values in the sentence weren't read. That's 31 of 277 false rows.
4. **Negation** on non-yes/no facts: a fix and a regression test.
5. **Pass 1 vs pass 2** under the shift test: keep pass 2 only if it wins.

### B: frontend and demo (`dev/b`)

1. **Honest claims chart:** use the strict judge's numbers, with no circular 100%.
2. **Show the controls and the shift test** on `/confidence`, once C exposes them in `/metrics`.
3. **The 09:00 video:** upload `sample/sample.csv` on the run page, with the architecture diagram on the same screen.

### C: platform (`dev/c`)

1. Merge `dev/c` into `integration` (controls, shift test, regularized engine).
2. `/metrics` gets `shift` (from `reports/shift_test.json`) and `controls` (what the control group showed on practice). Rerun the shift test for the current engine.
3. **Every** example in `contracts/claim-forms.md` and `value-forms.md` becomes a test; fix the validator to match all of them (4 mismatches found, none in today's claims).
4. Claim-confidence control: if the veto removes a large share of a group's candidates, lower that group's confidence by the same proportion.
5. Frontend start guide (where it goes is the team's choice), and clean-up (`test.csv`, `.claude/launch.json`).
6. Freeze: merge `integration` into `main`, run `check.sh` on a fresh clone of `main`, and open the PR "Git Happens" to QA-DNA before 11:00 on 29 Oct.
7. Merge A's and B's work when they report, after the checks.

## Contract for B (C adds to `GET /metrics`)

```json
{
  "labels": { "...": "as today" },
  "claims": { "...": "as today, plus strict_n, strict_right, strict_precision per group" },
  "shift": [
    { "scenario": "held-out subjects", "unseen": 382, "always_true": 0.825,
      "factors": { "true": 1.0, "false": 0.34 },
      "unseen_before": { "n": 366, "said": 0.810, "right": 0.803, "ece": 0.046, "brier": 0.148 },
      "unseen_after":  { "n": 366, "said": 0.802, "right": 0.803, "ece": 0.028, "brier": 0.143 } }
  ],
  "controls": { "control_answers": 298, "accuracy": 0.862, "said": 0.831, "ece_before": 0.031,
                "factors": { "true": 1.0, "false": 1.0 }, "false_share": 0.097 }
}
```

`shift` and `controls` may be missing; the page shows "not measured" then, never a made-up number.

## Freeze checklist

- [ ] `integration` has everyone's measured work; all tests pass
- [ ] `MINUTES=5 scripts/check.sh` passes on a fresh clone of `main`
- [ ] The control model is retrained after the last engine change (`scripts/train_control.py`)
- [ ] The frontend starts from the start guide; the video is recorded on `sample/sample.csv`
- [ ] The PR from `main` to QA-DNA is open, titled "Git Happens", before 11:00
- [ ] After 11:00: no pushes, and the PR stays open

## Open questions for the organisers

1. "Claims based on the 20k": are they **judged against** the whole universe (our veto covers that), or should they **use facts from** the 18,000 (then we build claims from facts several confident rows agree on)?
2. How are a wrong label, `unsure`, and confidence scored? This decides whether we ever answer `unsure`.
3. Does an invalidly worded claim score zero or count against us?
4. Is "what starts the frontend" a start guide, or do you need a script?

---

## Prompt for A

```
I'm person A (engine/ML) on team "Git Happens", Hype or Truth hackathon (QA DNA).
Repo: hype-arena-starter. I work only on branch dev/a; C merges it into integration.

FIRST, bring my branch up to date:
  git checkout dev/a && git fetch origin && git merge origin/integration && git push
integration now has: C's run-time controls (arena/controls.py, scripts/train_control.py),
the shift test (scripts/shift_test.py), and B's regularized engine (l2=10, min_hess=20).

GOAL: correctness on rows the engine has never seen, without breaking confidence.

The numbers to beat (honest: models trained without the rows they're tested on):
- out of fold (eval/train_model.py): accuracy 0.863, ECE ~0.03
- hidden rows (--honest): 337/380, lies caught 27/49
- shift test (.venv/bin/python scripts/shift_test.py, ~8 min):
    random pages 88.0% | latest pages 83.7% | NEW SUBJECTS 80.3% vs always "true" 82.5%
On subjects it never saw, the engine is worse than always answering "true".

Bugs reproduced (by C, from your brainstorm):
- "Hooly AI Pro does not cost €59 per month." -> true 0.925 (negation ignored)
- "...€59 per month and has 7,777,777 users." -> true 0.925, complete=True (clause lost)
- "The weather in the office was lovely..." -> true 0.847 with 0 facts read
Measured out of fold: 31 of 277 false rows lose facts in extraction (18 nothing read,
13 marked complete). Non-boolean negations are rare (~16 rows). Most missed lies have
their facts read fine but no evidence contradicts them.

PRIORITIES, one change at a time, each measured:
1. No evidence for a fact -> lean "true", confidence near the base rate (~0.8), not a
   confident "false". Target: new subjects > 82.5%.
2. No facts read -> no confident answer.
3. Lost clauses -> mark the extraction incomplete when values in the sentence were not read.
4. Negation on non-boolean facts: fix + minimal-pair regression tests.
5. Pass 1 vs pass 2 under the shift test; keep pass 2 only if it wins.

NOTE: nothing can happen "when the 18,000 arrive". After the freeze the system runs
alone; every decision must be made before it, with the shift test.

PASS CRITERIA for merging:
- shift test: new subjects > 82.5%, random >= 88.0%, latest >= 83.7%
- out of fold: accuracy >= 0.863, ECE <= 0.03; hidden rows >= 337/380, lies >= 27/49
- .venv/bin/python -m pytest -q passes; MINUTES=5 scripts/check.sh passes (Docker Desktop on)
- after retraining: .venv/bin/python eval/train_model.py (writes the models and
  eval/calibration_labels.json) AND .venv/bin/python scripts/train_control.py (~1.5 min)

RULES: don't edit arena/runner.py, arena/io.py, arena/generate.py, arena/validate.py,
arena/controls.py, Dockerfile, README.md, STATUS.md (C's). Keep label_rows' signature
(including models=). Runtime stays pure Python (only jsonschema), offline, no LLM.
Commits: no Co-Authored-By / Generated with Claude lines. Push dev/a only, then report to C:
branch/commit, numbers before -> after, tried and rejected.
```

## Prompt for B

```
I'm person B (frontend/demo) on team "Git Happens", Hype or Truth hackathon (QA DNA).
Repo: hype-arena-starter, Next.js app in frontend/. I work only on branch dev/b;
C merges it into integration.

FIRST, bring my branch up to date:
  git checkout dev/b && git fetch origin && git merge origin/integration && git push
  cd frontend && npm ci
(integration has my regularized engine and isCalibrated fix; C kept the cautious
claim formula: date compares 0.971, not 0.99.)

GOAL: /confidence shows honest, measured numbers, and the demo video is ready.

1. Honest claims chart (ConfidenceView.tsx, lib/types.ts, fixtures/metrics.json):
   - claim groups now have strict_n, strict_right, strict_precision (null if strict_n = 0)
   - "were right" = strict_precision with n = strict_n when strict_n >= 20; otherwise no
     bar, and the group reads "capped at 0.95: unseen rows can't check it"
   - the "Claims in calibrated types" tile counts strict-checked groups only and says so;
     it must not read like an average confidence
   - subtitle: "checked only against rows after each cut-off, which the generator never saw"
2. Controls and shift test (once C adds them to GET /metrics; shape in PLAN_FINAL.md):
   - a "Shift test" section: per scenario, right vs always-"true", said before -> after
     the control, ECE before -> after. Highlight that on new subjects the engine is
     below always-"true" (honest) and that the control lowered over-stated confidence.
   - a "Run-time controls" card: the control group (answers, right, said, factors).
   - if shift/controls are missing: "not measured", never a made-up number.
3. Demo for 09:00 (29 Oct): sample/sample.csv (20 rows, labels empty) uploaded on the
   run page with the architecture diagram on the same screen; check it end to end with
   the real API (.venv/bin/uvicorn api.main:app --port 8000) and npm run dev.

TEST: npm run lint, npx tsc --noEmit, npm run build; live: /confidence, /claims, the run page.
RULES: don't touch api/, arena/, scripts/, eval/, Dockerfile, README.md, STATUS.md.
Show no number without a measurement behind it. Commits: no Co-Authored-By /
Generated with Claude lines. Push dev/b only, then tell C, with a screenshot of /confidence.
```

## Prompt for C

```
I'm person C (platform) on team "Git Happens", Hype or Truth hackathon (QA DNA).
Repo: hype-arena-starter. I work on dev/c and I alone merge dev/* into integration.

FIRST: git checkout dev/c && git fetch origin && git merge origin/integration

Tasks, in order, each committed on dev/c, then merged into integration only after all
checks pass (pytest, MINUTES=5 scripts/check.sh in Docker, numbers not worse):
1. Merge dev/c into integration (controls, shift test, regularized engine).
2. GET /metrics: add "shift" (reports/shift_test.json plus always_true per scenario) and
   "controls" (the control group on practice). Rerun scripts/shift_test.py for the current engine.
3. Every example in contracts/claim-forms.md and value-forms.md as a test; fix the
   validator to match all (4 known mismatches); confirm the 1,000 claims are unchanged.
4. Claim-confidence control: lower a group's confidence by the share of its candidates
   the veto removes.
5. Frontend start guide (location: team decision); clean-up (test.csv, .claude/launch.json).
6. Merge A's and B's reports after checking their numbers against PLAN_FINAL.md.
7. Freeze: integration -> main, check.sh on a fresh clone of main, PR "Git Happens" to
   QA-DNA before 11:00 on 29 Oct. No pushes after 11:00.
Keep STATUS.md updated after every merge. Don't edit README.md without the team.
Commits/PR: no Co-Authored-By / Generated with Claude lines.
```
