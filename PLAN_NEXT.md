# Git Happens — NEXT PLAN: SCORE ON EVERY CRITERION

**Team:** 3 people · 3 laptops · 3 AI accounts
**Challenge:** QA DNA — Hype or Truth, NEXXT AI Hackathon
**Written:** 28 October 2026, after the first checkpoint

> Roles, branches and contract v1 from `hype_arena_PLAN_FINAL.md` stay unchanged. The live state is in `STATUS.md`.
> The team decides the timing; this plan sets the goals, owners and acceptance criteria.

**In short:** we are judged on five criteria. The work below targets each one. The main change from before: **confidence is about honesty, not maximum.** Self-evaluation rewards a team that knows how good its system is, so a confidence must equal how often we are right. We raise it only by being right more often.

## 1. How we are judged

| Weight | Criterion | What it means for us |
|---|---|---|
| **30%** | **Correctness**: how right it is on data it hasn't seen | The labels on the ~18,000 unlabelled rows, and the 1,000 claims being true |
| **25%** | **Architecture**: the system does the work itself, not an LLM | Rules + small trained models, no LLM; it must be shown, documented and runnable |
| **20%** | **Demo**: run on the sample released Thursday 09:00, shown in the video | A live run of the 20 sample rows in our frontend, next to the diagram |
| **15%** | **Self-evaluation**: how well the team knows how good it is | Calibrated confidence, plus our own stated prediction of our score |
| **10%** | **Business mentoring**: problem, users, value, adoption | A short, clear pitch inside the video |

The README says both the labels and the claims are judged. Whichever way the organisers split them between Correctness and Self-evaluation, the strategy is the same: **be right more often, and make confidence equal to how often we are right.**

## 2. What we measured

**Claims:** built from data before a cut-off date, checked against the data after it, at two cut-offs:

| Claim type | Confidence today | Actually right |
|---|---|---|
| change | 0.80–0.95 | 100% (166 / 166) |
| at_event | 0.82–0.95 | 100% (200 / 200) |
| compare | 0.82–0.96 | 99.8% (451 / 452) |
| fact ("X is Y on 29 Oct") | 0.83–0.91 | **65–76%** (95 / 134): changing numbers go stale |
| relation | 0.88–0.92 | not measurable (6 claims) |

Today's claim confidences are 12 fixed values chosen by hand. The safe types are under-confident, and `fact` is over-confident.

**Labels:** the engine on the 380 practice rows `check.sh` hides (329 right, 86.6%; always `true` would score 85%):

| Label, confidence | Rows | Actually right |
|---|---|---|
| true, 0.9+ | 145 | 98% |
| true, 0.8–0.9 | 143 | 88% |
| true, 0.6–0.8 | 66 | 71% |
| true, 0.5–0.6 | 13 | **38%** |
| false, any | 13 | 69% |

Only 9 of the 49 false rows are caught. `unsure` is never predicted.

## 3. Work by criterion

### Correctness (30%): be right
- **A:** catch more false sentences; fix the `true` 0.5–0.6 band; use agreement across the whole input at runtime (`label_rows`), without counting copies as independent sources or letting a row confirm itself.
- **C:** keep only claim types that backtest at ≥ 98%; drop `fact` claims about values that change; fill the 1,000 with change, at_event and compare claims; switch the runner to A's `label_rows`.

### Architecture (25%): show that the system does the work
- **A:** a short write-up of each engine stage and what it learns: value parser, naive Bayes extraction, temporal knowledge base, logistic regression verdict.
- **B:** every box of the diagram names its technique; the replay shows real numbers for every step.
- **C:** a README section "How it works, and why there is no LLM"; a `Dockerfile` that passes `scripts/check.sh`, so the architecture runs and is not only drawn.

### Demo (20%): the sample, live, in the video
- **B:** the demo script; rehearsal on `test.csv`; on Thursday, the live run on `sample/sample.csv`, recorded from `npm run build && npm start` (no dev indicator).
- **C:** everything merged, tested and running on one laptop before the sample is released.

### Self-evaluation (15%): know how good we are
- **A:** calibrate the label confidence on out-of-fold predictions, so that 0.9 means right about 90% of the time; report the calibration error (ECE) before and after.
- **C:** a claim backtest script; each claim's confidence set from its group's measured accuracy (lower bound, never above what was measured).
- **B:** a confidence chart in the UI: "we said X → we were right Y", for labels and per claim type.
- **Everyone:** our **predicted score**, written before the final run and stated in the README and the video, e.g. *"we expect about 85% of labels right, 98%+ of claims true, confidence calibrated within ±3%."*

### Business mentoring (10%): problem, users, value, adoption
- **B + C:** about 30 seconds of the video.
  - **Problem:** companies publish outdated or false claims.
  - **Users:** marketing and legal review, documentation teams, chatbot QA.
  - **Value:** an explainable, date-aware checker that cannot invent facts.
  - **Adoption:** it runs on a laptop, offline, with no LLM costs.

## 4. Responsibilities and files

| Person | Owns | New in this plan |
|---|---|---|
| **A — engine and ML** | `arena/classify.py`, `extract.py`, `truth.py`, `values.py`, `lexicon.py`, `arena/ml/`, `eval/` | calibration map in `model.json`; `eval/calibration_labels.json`; engine write-up |
| **B — frontend, demo** | `frontend/` (including C's 28 Oct additions: the Claims page, claim steps, evidence text) | confidence chart; demo script; video |
| **C — platform** | `arena/generate.py`, `validate.py`, `render.py`, `runner.py`, `io.py`, `api/`, `Dockerfile`, `requirements*.txt`, `README.md`, `STATUS.md` | `scripts/backtest_claims.py`; `reports/claims_calibration.json`; `GET /metrics` |

Nobody edits another member's files without asking. Only C edits `requirements.txt`; A and B send C their dependencies.

## 5. Contract additions (v1 stays; new files and fields only)

**`eval/calibration_labels.json`** (A writes, the API serves):

```json
{"method": "isotonic", "fitted_on": "out-of-fold practice, page-grouped 5-fold",
 "bins": [{"label": "true", "from": 0.9, "to": 1.0, "n": 145, "accuracy": 0.98, "confidence": 0.97}],
 "ece_before": 0.06, "ece_after": 0.02}
```

**`reports/claims_calibration.json`** (C writes):

```json
{"cutoffs": ["2026-05-01", "2026-07-01", "2026-09-01"],
 "groups": [{"group": "change", "n": 166, "right": 166, "precision": 1.0, "confidence": 0.98}]}
```

**`GET /metrics`** (C) returns `{"labels": <calibration_labels or null>, "claims": <claims_calibration or null>}`. A missing file gives `null`; the API never invents numbers. B builds against a fixture of this shape, marked as simulated.

## 6. Rules for confidence

- A confidence equals measured accuracy on data the model did not learn from: out of fold for labels, after the cut-off for claims.
- Never raise a confidence without a measurement behind it. Raise accuracy instead.
- If the organisers say how `unsure` is scored, the team sets `ARENA_UNSURE_BELOW` from it; until then, every label stays firm.
- Practice is about 10% of the final input, so every measurement is an estimate. Say so in the README and the video; that is part of self-evaluation.

## 7. Acceptance criteria

**Correctness**
- Labels: accuracy on the hidden rows and in cross-validation not lower than today (329 / 380; 84.8%); false recall above 9 / 49, reported with false precision.
- Claims: every type kept is ≥ 98% right at each backtest cut-off; exactly 1,000, all passing the validator, with a reserve of at least 150.

**Architecture**
- The README explains each stage and why no LLM is used; the diagram names each technique; `scripts/check.sh` passes offline as user 10001.

**Demo**
- The video shows the diagram, a live run of the sample, evidence for a verdict, the claims, and the confidence chart.

**Self-evaluation**
- Label ECE ≤ 0.05 out of fold; no bin with ≥ 20 rows where accuracy is more than 0.05 below confidence.
- Each claim's confidence is at most its group's measured accuracy, and within 0.03 of it.
- A written prediction of our score, with how it was measured, in the README and the video.

**Business**
- The video names the problem, the users, the value and why it would be adopted.

## 8. How we work on branches

Branches are named after people, not technologies: each of us now works across several criteria.

| Branch | Who works on it | What it holds |
|---|---|---|
| `dev/a` | A | A's work: engine, ML, calibration, engine write-up |
| `dev/b` | B | B's work: frontend, confidence chart, demo, video |
| `dev/c` | C | C's work: claims, backtest, runner, API, Docker, README |
| `integration` | C merges only | all three combined, tested and measured |
| `main` | C, once, at the freeze | what we submit; the PR to QA-DNA goes from here |

The first-phase branches (`ML-and-python`, `team/frontend`, `teamapi`) stay on GitHub untouched, as a record. Nobody works on them anymore, and nobody deletes them during the hackathon.

### Once, at the start: everyone on the same base

1. A and B check that nothing on their old branch is missing from `integration`; anything missing, C merges into `integration` first.
2. C commits and pushes `integration`, so the plan, `STATUS.md` and the latest code are visible to all.
3. C creates `dev/a`, `dev/b` and `dev/c` from that `integration` and pushes them.
4. Each person switches to their branch:

```sh
git fetch
git checkout dev/<you>              # dev/a / dev/b / dev/c
cd frontend && npm ci               # whenever frontend/package-lock.json changed
```

### The loop

```
 your branch ──(work, commit, push)──► post in the chat ──► C merges into integration ──► tests + measurements
       ▲                                                                                       │
       └─────────────── git merge origin/integration into your branch ◄────────────────────────┘
```

1. Work only on your own branch, and only in your own files (section 4).
2. Commit small, push often. Pushing your own branch affects nobody.
3. When something is ready, post the update template (section 10), with what you measured before → after.
4. C merges your branch into `integration` and runs the Python tests, the frontend build, the claim backtest, the official checker and the label measurements, then updates `STATUS.md`.
   - Everything passes: C pushes `integration`.
   - Something breaks, or a measured number goes down: C reports it; the author fixes it **on their own branch**. Nobody patches another member's code in `integration`.
5. After every merge, everyone runs `git merge origin/integration` into their branch, so nobody drifts far behind.

### Rules

- Only C commits on `integration`, and only merges. Nobody works directly there, C included.
- Stay in your own files; for a change in someone else's file, ask its owner.
- No force-push and no rebase of a pushed branch.
- A merge conflict stops the merge: C asks the two authors which version is right, and never guesses.
- `main` changes once, at the freeze: C merges `integration` into it and opens the PR to QA-DNA.
- No Claude attribution lines (`Co-Authored-By`, "Generated with …") in commits or PRs.

## 9. Prompts for the three AI accounts

Each person sends their AI this file, `STATUS.md`, their prompt below, and the official `README.md` and `contracts/`. Every prompt ends with the same git rules, so each AI follows section 8.

### Prompt A — engine and ML

> You work on the engine of a hackathon system that labels sentences about a fictional company as true, false or unsure on their date, with a confidence. Read PLAN_NEXT.md and STATUS.md first. You own arena/classify.py, extract.py, truth.py, values.py, lexicon.py, arena/ml/ and eval/; do not edit other files, and keep the contract v1 functions unchanged.
>
> Goals, in order: (1) Correctness: catch more false sentences (9 of 49 today) and fix the `true` labels at confidence 0.5–0.6, which are right only 38% of the time; study those rows before changing anything. (2) Self-evaluation: fit a calibration map (isotonic or binned) from the model's probability to out-of-fold accuracy, store it in arena/ml/model.json, apply it in decide(), and report ECE before and after; write eval/calibration_labels.json in the shape given in PLAN_NEXT.md section 5. (3) Make label_rows' corroboration safe: no row may confirm itself, and copies do not count as independent sources. (4) Write a short description of each engine stage for the README.
>
> Measure only out of fold or on rows the model did not learn from. Never raise a confidence without a measurement. No LLM at runtime; standard library only unless you agree a dependency with C. Report the numbers you measured, before and after, and what you could not fix.
>
> Git: work only on the branch `dev/a`. Before you start, and after every merge C announces, run `git pull` then `git merge origin/integration`. Commit small, with plain messages and no Co-Authored-By or "Generated with" lines; push only `dev/a`. Never commit to `integration` or `main`, never force-push, never rebase a pushed branch. When a piece is ready, write the update for the team chat: what works, measured before → after, interfaces changed (no / what), blockers. On a merge conflict in a file you do not own, stop and ask.

### Prompt B — frontend, demo and video

> You work on the frontend (Next.js + TypeScript + Tailwind) of a hackathon system that labels sentences about a fictional company as true, false or unsure on their date, and writes 1,000 new true claims. Read PLAN_NEXT.md and STATUS.md first. You own frontend/; do not implement Python, ML or truth logic, and keep the existing API contract.
>
> Goals: (1) A confidence chart: "we said X → we were right Y", for labels and per claim type, from GET /metrics in the shape of PLAN_NEXT.md section 5; build it against a fixture first, clearly marked as simulated, and never as a hidden fallback. (2) Name each diagram box's technique (value parser, naive Bayes extraction, temporal knowledge base, logistic regression verdict, template generator, rule validator). (3) Review the Claims page, the claim steps in the replay and the evidence text that C added on 28 Oct, and take ownership of them. (4) Update Next.js to a patched 15.5.x. (5) Write a 2–3 minute demo script: problem, users and value; the diagram; a live upload of the sample; one sentence true in August and false in January; its evidence; the claims; the confidence chart; our predicted score; adoption. Rehearse on test.csv; record from npm run build && npm start.
>
> Run lint, type-check and build before you push. Report what you changed and what you checked.
>
> Git: work only on the branch `dev/b`. Before you start, and after every merge C announces, run `git pull` then `git merge origin/integration`, then `npm ci` in frontend/ if frontend/package-lock.json changed. Commit small, with plain messages and no Co-Authored-By or "Generated with" lines; push only `dev/b`. Never commit to `integration` or `main`, never force-push, never rebase a pushed branch. When a piece is ready, write the update for the team chat: what works, what you checked, interfaces changed (no / what), blockers. On a merge conflict in a file you do not own, stop and ask.

### Prompt C — platform

> You work on the platform of a hackathon system that labels sentences about a fictional company as true, false or unsure on their date, and writes exactly 1,000 new true claims. Read PLAN_NEXT.md and STATUS.md first. You own arena/generate.py, validate.py, render.py, runner.py, io.py, api/, the Dockerfile, requirements*.txt, README.md and STATUS.md; do not edit the engine or the frontend without asking.
>
> Goals: (1) Correctness of claims: write scripts/backtest_claims.py (cut-offs 1 May, 1 July, 1 September; claims built from rows before the cut-off, checked against rows after it), write reports/claims_calibration.json, keep only claim groups at ≥ 98% at every cut-off, drop fact claims about values that change, and keep exactly 1,000 with a reserve of at least 150. (2) Self-evaluation: set each claim's confidence from its group's measured accuracy (Wilson lower bound, never above the measurement), and serve both calibration files at GET /metrics. (3) Switch the runner to A's label_rows, keeping the deadline, SIGTERM and atomic-write behaviour. (4) Architecture: a README section on how the system works and why there is no LLM, the start guide, and a Dockerfile that passes scripts/check.sh offline as user 10001. (5) Keep STATUS.md current after every merge.
>
> Every claim must still pass the validator; run the full test suite and the official checker before each push. Report measured numbers, before and after.
>
> Git: do your own work only on the branch `dev/c`; before you start, run `git pull` then `git merge origin/integration`. You are also the integrator: when A or B announce a piece, merge their branch (`dev/a`, `dev/b`, and your `dev/c`) into `integration` with `git merge --no-ff`, never with direct commits; run the Python tests, the frontend lint, type-check and build, the claim backtest, the official checker and the label measurements; update STATUS.md; push `integration` only if everything passes and no measured number went down, otherwise report to the author and let them fix it on their branch. On a conflict, stop and ask the two authors; never guess. Plain commit messages, no Co-Authored-By or "Generated with" lines; never force-push or rebase a pushed branch. `main` changes once, at the freeze, by merging `integration`; the PR to QA-DNA goes from `main`.

## 10. Communication

Ask the organisers how confidence and `unsure` are scored; the answer sets `ARENA_UNSURE_BELOW`. At each merge, each person posts:

```text
Who / branch / commit:
What works:
Measured (before → after):
Interfaces changed: no / what
Blocker / request to a teammate:
Next deliverable:
```

## 11. Checklist

- [ ] Everyone has read this plan and `STATUS.md`; each AI has its prompt.
- [ ] Question about scoring sent to the organisers.
- [ ] Correctness: false sentences, the 0.5–0.6 band, safe claims only.
- [ ] Architecture: README "how it works", technique names on the diagram, Dockerfile passing `check.sh`.
- [ ] Demo: script written and rehearsed; sample run and recorded.
- [ ] Self-evaluation: label calibration, claim backtest, confidence chart, written predicted score.
- [ ] Business: problem, users, value and adoption in the video.
- [ ] PR to QA-DNA opened before 11:00 on 29 October.
