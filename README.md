# Git Happens: Hype or Truth

Our system answers one question about Hooly: **was this true on that date?** It labels each row `true` or `false`, and gives each label a confidence we measured on rows the model never saw. It also writes 1,000 new claims, each checked by two independent checkers.

There is no language model in the container. The image is ~50 MB, its only dependency is `jsonschema`, and it runs offline.

## Running it

**The batch run**, as the judges run it, starts from the [`Dockerfile`](Dockerfile): it reads `/universe/`, and writes `/output/output.csv`.

```sh
scripts/check.sh            # build the image and run it on the practice data, with every fifth label hidden
```

**The frontend** needs Python 3.12 and Node 20+:

```sh
scripts/start.sh            # API on :8000, app on http://localhost:8080; Ctrl+C stops both
```

Use Vite's server for the app: only it forwards `/api` to the engine. To try it on rows with known answers, upload [`data/test/demo.csv`](data/test/demo.csv) on **Live run**; the answers are in `demo_key.csv`. More detail is in [`frontend/README.md`](frontend/README.md).

**The tests:**

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q         # 639 tests, 206 of them the examples in claim-forms.md and value-forms.md
```

## How it works

```
universe.csv ─► values + names ─► fact extraction ─► temporal knowledge base ─► boosted trees + Platt ─► label, confidence
                                                              │
                                                              └─► claim templates ─► validator ─► 1,000 claims
                                    run-time controls: a held-out control group can only lower confidence
```

### Labelling a row

| Stage | File | Technique |
|---|---|---|
| Value parser | `arena/values.py` | Rules: `value-forms.md`, implemented exactly |
| Name matcher | `arena/lexicon.py` | The lexicon's names and aliases, longest first |
| Fact extraction | `arena/extract.py` | Naive Bayes over the words around each value, with page context |
| Temporal knowledge base | `arena/truth.py` | Each fact's history; evidence features at the sentence's date |
| Verdict | `arena/ml/model.py` | Gradient-boosted trees, Platt calibration, one round of self-training |

Prices, versions and headcounts change during the year, so a sentence is checked against what the evidence said **on its own date**, not against the latest value. The engine labels the whole input once, adds the labels it is confident about as evidence, and labels everything again. A row's own page never counts as evidence for it. Every verdict carries its reason and the ids of the rows it rests on. Details: [`eval/ENGINE.md`](eval/ENGINE.md).

### Writing 1,000 claims

- **Templates.** `arena/generate.py` builds claims from facts that rows labelled true agree on: date compares, changes, values at an event, one-time dates and relations. It never writes values that can go stale, or dates that move (`latest_*`, `next_*`, `planned_*`).
- **Our validator.** `arena/validate.py` checks every claim against `claim-forms.md`, `entry.schema.json` and the lexicon.
- **An independent referee.** `scripts/referee.py` was written from `contracts/` alone, without reading our validator. It accepts every official example, rejects 6,721 of 6,724 deliberately broken claims, and rejects none of our 1,000.
- **Confidence from a backtest.** `scripts/backtest_claims.py` builds claims from the rows dated before a cut-off (1 May, 1 Jul and 1 Sep). It then judges them only on rows dated after the cut-off, which the generator never saw. A claim's confidence is the Wilson lower bound (95%). A type that later rows can't check is capped at 0.95.

### Checking itself during the run

The run can't be adjusted after the freeze, so `arena/controls.py` checks it on the real input:

- **A control group.** 381 practice rows are hidden from a control model. In the run, it labels them in the context of the real input. Where the control group shows a label's confidence is over-stated, that confidence is lowered. It is never raised.
- **A distribution monitor.** The log compares the share of `false` in the input with the share in the control group.
- **A claim veto.** Input rows labelled `true` at 0.9 or more join the evidence. A claim they contradict is replaced from the reserve, and its group's confidence drops by the share it lost.

The run also writes a complete table before it starts labelling, and then rewrites it atomically. A bad row costs only that row. If the claim generator fails, the run uses `data/claims_fallback.csv`.

## How good it is

Every number below comes from rows the model did not learn from, with whole pages held out at a time.

| What | Result | How |
|---|---|---|
| Labels right | **87.0%** of 1,897 (always `true`: 83.3%) | Page-grouped 5-fold, out of fold (`eval/train_model.py`) |
| Lies caught | 118 of 277 false rows | Same |
| Calibration error (ECE) | **0.027** | Platt scaling, cross-fitted (`eval/calibration_labels.json`) |
| Date-compare claims | **133 / 133** right on later rows; confidence 0.972 | Strict backtest (`reports/claims_calibration.json`) |
| One-time-date claims | 25 / 25 right on later rows; confidence 0.867 | Same |
| Change and at-event claims | 350/350 and 449/449 by the full judge; later rows can't check them, so capped at 0.95 | Same |
| Control group | 369 answers, 89.4% right; said 0.85 | `reports/controls.json` |
| Run time | ~11 s on practice; 131 s on a synthetic 20,000-row input, of the 30 minutes | `scripts/check.sh` limits: 2 CPUs, 6 GiB, offline |

**Shift test** ([`scripts/shift_test.py`](scripts/shift_test.py)). About 20% of practice is held out, the models are trained only on the rest, and the run is replayed with its controls:

| Unseen part | Right | Always `true` | ECE after the control |
|---|---|---|---|
| Random pages | 88.8% | 83.9% | 0.062 |
| Latest pages (time shift) | 83.5% | 81.5% | 0.034 |
| Held-out subjects (new products) | **79.5%** | **82.5%** | 0.031 (from 0.040) |

`scripts/check.sh` reports 340 of 380 hidden rows right, but that is an upper bound: the image's model was trained on those rows. We report 87.0%.

### Our predicted score

- **Labels:** about 87% right; between 79.5% and 88.8% across the shift test.
- **Claims:** about 95% true (mean confidence 0.959).
- **Confidence:** within about 3 points of how often we are right.
- **Caveat:** practice is about 10% of the final input. On subjects we have never seen, we expect to do worse.

## Where it is weak

- **New subjects.** On products it has never seen, the engine is below always answering `true` (79.5% vs 82.5%).
- **Made-up numbers.** It catches 43% of false rows. It is weakest on a number the fact never held, where the rules say false and the model overrules them at low confidence.
- **Unchecked claim types.** 544 of the 1,000 claims (at_event and change) carry a 0.95 cap, not a measurement.
- **No `unsure`.** We never answer `unsure`: every rule we tried lost more right answers than it saved. If a wrong answer costs at least 1.5× what a right one earns, set `ARENA_UNSURE_BELOW=0.55`.

## Tried, measured and left out

| Experiment | Result |
|---|---|
| 5-model ensemble (`eval/train_ensemble.py`) | Fewer lies caught (143 → 114 out of fold); not better on the shift test. Its disagreement does flag wrong answers (AUC 0.80) |
| Synthetic lies (`eval/augment.py`) | Lies caught fell 118 → 104; 5 of 6 shift-test cells got worse |
| A confidence model on the engine's answers (`arena/confidence.py`) | ECE 0.062 → 0.016 on random pages, but over-confident on new subjects (0.031 → 0.083) |
| A stricter contradiction rule | Out of fold 0.870 → 0.866, lies caught 118 → 113 |

## Why no language model

- The rules say the system may not be an LLM.
- The universe contradicts the real world on purpose, so a pretrained model would bring in facts the universe doesn't hold.
- About 1,900 labelled sentences are enough for small models and too few for large ones.
- Small models run offline in seconds and explain every answer.

LLMs helped us write the code. Nothing in the image is one.

## What is where

| Path | What |
|---|---|
| `arena/` | The batch run: engine, claims, controls, runner (`python -m arena.runner`) |
| `api/` | FastAPI for the frontend: `/health`, `/predict`, `/claims`, `/metrics` |
| `frontend/` | The dashboard: overview, live run, architecture, claims, confidence, dataset |
| `eval/`, `scripts/`, `reports/` | Training, backtests, the shift test, the referee, and their results |
| `data/test/` | Synthetic test files with answer keys (not in the image) |
| `STATUS.md` | The team's log, with every measurement and decision |

## Team

Git Happens:
- **A:** the engine.
- **B:** the frontend, the referee and the stress tests.
- **C:** the claims, the run and its controls, the API and the merges.

---

## The challenge (from the organisers)

### [hype-arena.vercel.app](https://hype-arena.vercel.app/)

### The universe

**Hooly** is a fictional company in a fictional universe, made for the QA DNA challenge of the NEXXT AI Hackathon. Its name alludes to Hooli, the tech giant of the TV series *Silicon Valley*. Its products carry the names of real Google products, used fictitiously: nothing here describes those products or their makers. Its people carry the names of the series' characters with a few letters changed.

Hooly's people, events, decisions and figures are invented, and the universe departs from the series and from Google's real history on purpose. **The truth is what the universe says.** A system that fills gaps from the web, or from what a pretrained model already knows, learns facts the universe contradicts.

The universe is a year of Hooly's pages, docs, posts, decks and press releases, in which prices, headcounts, dates and names change, and some pages lie. You get a part of it as sentences, each labelled.

### The task

Build a system that does two things with rows about Hooly, each with how sure your system is:

- **It labels rows.** Given rows of the universe, some labelled and some not, it labels each unlabelled row `true`, `false` or `unsure`.
- **It writes new content.** It writes exactly 1,000 new claims about Hooly that connect what the universe says, every one of them true.

How you build it is yours to decide.

- **LLMs may help you build your system,** and make what it learns from, but the system itself may not be an LLM.
- **Fork this repository and work in your fork,** so we can follow your work. Forks are public.
- **Your system has a frontend:** a working page that shows the architecture of your system as a diagram and runs the system live on rows you give it. Start it however you like: your video shows it running.
- **At 09:00 on 29 Oct we add a sample of 20 rows to this repository,** as one CSV file, `sample/sample.csv`: new rows, in the shape of the run's input with every `label` empty (`id`, `text`, `date`, `label`). The video you hand in at 11:00 shows your frontend running your system live on them, beside its architecture diagram.
- **Your submission is a pull request** from your fork to this repository, one per team, titled with your team's name and opened before 11:00 on 29 Oct. It holds both the `Dockerfile` we run your system from, as [`contracts/README.md`](contracts/README.md) says, and what starts your frontend. What it holds at 11:00 is what we run: a push to it, or closing it, after 11:00 disqualifies the team.
- **We run every team's system** after 11:00, offline, for up to 30 minutes, on about 20,000 rows of the universe, the practice rows among them with their labels. It hands in one table, `/output/output.csv`: a label for each of the roughly 18,000 unlabelled rows and exactly 1,000 new claims, every one true, and we judge both. How it runs, what it reads and what it hands in is in [`contracts/README.md`](contracts/README.md).

### What is here

| Path | What |
| --- | --- |
| `data/practice.csv` | The practice dataset: one row per sentence of the practice part of the universe, each labelled `true`, `false` or `unsure`, with the facts it states |
| `data/lexicon.json` | The subjects the dataset names, with their aliases and attributes, and the events |
| `contracts/` | What you get, how we run your system and what it hands in |
| `sample/sample.csv` | From 09:00 on 29 Oct: the 20 rows of the sample, unlabelled |
| `scripts/check.sh` | Runs your system as we will, on the practice data, and checks its table |

### Check your system

`scripts/check.sh` builds the image from your `Dockerfile` and runs it as we will: offline, as user 10001, on a read-only root, with 2 CPUs and 6 GiB, until it exits or 30 minutes pass. Its input is the practice dataset in the run's shape, with every fifth row's label hidden. It then checks your table's columns, ids, lengths, labels and confidences, that it holds exactly 1,000 new claims, and counts your labels on the hidden rows against the practice labels. It needs Docker and Python 3.

It does not check a claim's text against `claim-forms.md`, its form against `entry.schema.json`, or its names against the lexicon: we check those after the run. And an image that holds `data/practice.csv` knows the hidden labels, so the label count here is an upper bound.

```sh
scripts/check.sh                 # build the image and run it
scripts/check.sh my-image:tag    # run an image you built
MINUTES=5 scripts/check.sh       # a shorter run
```

A run that passes here can still fail ours on what the practice data does not hold.
