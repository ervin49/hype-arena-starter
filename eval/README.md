# Engine (A): how to call it, what it scores, where it is weak

Branch `dev/a`. Python 3.12, standard library only: nothing to add to `requirements.txt`. How each stage works, for the README: [ENGINE.md](ENGINE.md).

## Calling it (C: runner and API)

Contract v1 functions, unchanged:

```python
from arena.truth import build_kb, check_fact
from arena.extract import build_extractor, extract
from arena.classify import classify

kb = build_kb(practice_rows, lexicon)          # practice_rows WITH form (data/practice.csv in the image)
extractor = build_extractor(practice_rows, lexicon)
check = lambda fact, date: check_fact(fact, date, kb)
prediction = classify(row, extract(row, lexicon, extractor), check)
```

**Use this for the batch run instead** (PLAN_NEXT, Correctness, C): it does the same, plus page context, corroboration and self-training across the whole input:

```python
from arena.classify import label_rows
predictions = label_rows(universe_rows, practice_rows, lexicon)   # universe in input order
# -> one prediction per row with an empty label; labelled rows are skipped
```

- `universe_rows`: `/universe/universe.csv` as read, **in file order**. Labelled rows are kept: they give context ("It costs €59 a month" takes its subject from the rows before it on the same page) and corroboration.
- `practice_rows`: `data/practice.csv` copied into the image, with `form`. The runtime input has no `form`.
- `arena/ml/model.json` and `arena/ml/model_pass2.json` must be in the image. Without the first, `classify` falls back to the rules alone, which are much worse (below).
- `label_rows` **self-trains**: a second pass re-checks every row against the evidence plus the rows the first pass is confident about (P ≥ 0.85). A row's own page, and copies of its sentence anywhere in the input, never count for it; copies count as one source. Only `label_rows` does this. Calling `classify` row by row gives pass 1 only.
- Time: about 40 s and under 200 MB for 20,000 rows on a laptop (both passes).
- `ARENA_UNSURE_BELOW` (env, default `0`): a firm label whose probability is below it is exported as `unsure`. `0` keeps every label firm. This is a team decision once the scoring is known.

Export: `label` and `confidence` (`None` → empty cell). Everything else is for display.

## What a prediction holds (B: display)

```json
{"id": "...", "label": "true", "confidence": 0.92, "evidence_ids": ["p-1755", "..."],
 "reason": "Supported: Hooly AI Pro price: last stated so on 2026-10-07.",
 "probs": {"true": 0.92, "false": 0.054, "unsure": 0.026},
 "first_pass": {"label": "true", "confidence": 0.97},
 "checks": [{"fact": "Hooly AI Pro price = EUR 59/month", "status": "supported", "case": "after_last_match", "...": "..."}],
 "extraction": {"facts": [...], "complete": true, "issues": [], "scores": [7.1]}}
```

`evidence_ids` are practice row ids, which the UI can show as sources. `checks[].features` is diagnostic only.

## Results

All measured on practice rows the models did not learn from: page-grouped 5-fold cross-validation, where a held-out page gives nothing to the base, the extractor or the models.

**Hidden rows, as `scripts/check.sh` hides them** (`python3 eval/eval_hidden.py --honest`: both models retrained on the visible 80% first):

| | Right | False caught | False precision | ECE |
|---|---|---|---|---|
| always `true` | 331 / 380 | 0 / 49 | – | – |
| runner path today (row by row, pass 1) | 336 / 380 | 17 / 49 | 17 / 23 | 0.044 |
| `label_rows` (pass 2) | **339 / 380** | **31 / 49** | 31 / 48 | 0.056 |

Without `--honest`, the shipped models have seen the hidden rows: 340 / 380 and 29 / 49 caught, an upper bound like `check.sh`'s own count (PLAN_NEXT's 329 / 380 was measured that way).

**Regularization** (28 Oct): the boosted trees now use `l2=10, min_hess=20` instead of `l2=1, min_hess=4`. Each practice row is trained on once per labelled ratio, so the old leaves could rest on one row. Before → after on the hidden rows (`--honest`, `label_rows`): 329 → 337 right, false precision 22/39 → 27/41, and the over-confident `false` 0.5–0.6 bin (said 0.52, right 0.39) is gone. Out of fold, log loss fell in 5 of the 6 pass × ratio cells (mean 0.372 → 0.369). The ECE on the hidden rows rose (0.037 → 0.059), from `true` labels at 0.5–0.8 that are right *more* often than they say: under-confidence, on bins of about 25 rows. Fewer rounds (100, 150), depth 1, depth 3, `l2=30, min_hess=40`, 500 rounds and logistic regression were measured too and were no better.

**Rare attributes and subject origin** (28 Oct, PLAN_FINAL). 172 of the lexicon's 514 subject–attribute pairs have at most 2 practice facts. The extractor's naive Bayes smoothed each attribute toward uniform, so a rare attribute could not beat "no fact": the value was dropped or given to a subject with more data. Each attribute is now smoothed toward the words of all facts (`NB_PRIOR = 1000`, a broad optimum from 300 to 2,000 in `eval_extract.py --prior`): rows extracted exactly 0.747 → 0.816, F1 0.818 → 0.867. Each extraction also says where each fact's subject came from (`subject_from`: named, context, other), a feature of the label model. Before → after, models trained without the rows tested:

| Test | Before | After |
|---|---|---|
| Out of fold, pass 2, 100% | 0.863, 110 / 277 false caught | **0.870**, 118 / 277; ECE 0.027, no low bin |
| Hidden rows (`--honest`) | 337 / 380, 27 / 49 caught | **339 / 380, 31 / 49** |
| Shift test, random pages | 0.880 | **0.888** |
| Shift test, latest pages | 0.837 | 0.835 (1 row; about 30 rows flip between retrainings) |
| Shift test, new subjects | 0.803 | 0.795 (always `true`: 0.825) |
| New subjects, evidence shift only | 0.839 | **0.861** |

"New subjects" removes two things at once: the labelled evidence about the subjects, and every example the extractor had of their attributes. Only the first can happen in the run, because practice holds all 514 pairs. Most of its wrong `false` labels are values put on a neighbouring subject ("Hooly Chrome starts in 1.9 s" read as Hooly AI Pro's free trial). "Evidence shift only" keeps the held-out subjects' labels away but lets the extractor learn forms (what a sentence states, not whether it is true) from every other page, as in the run.

**Simulated runs** (`python3 eval/train_model.py`). The run has about 10% labelled evidence and 90% unlabelled text; the simulation makes only a fraction of the other pages labelled evidence. Accuracy after calibration, all 1,897 rows out of fold:

| Labelled evidence | Pass 1 | Pass 2, self-trained | False recall, pass 1 → 2 | ECE, pass 2 |
|---|---|---|---|---|
| 10% (the run's ratio) | 0.844 | **0.847** | 0.14 → 0.26 | 0.023 |
| 25% | 0.849 | **0.857** | 0.26 → 0.33 | 0.018 |
| 100% (dense evidence, as in the live demo) | **0.873** | 0.870 | 0.43 → 0.43 | 0.027 |

"Always true" scores 0.833. The simulated runs have far less evidence than the real one, so their absolute numbers are pessimistic.

**Calibration** (PLAN_NEXT, Self-evaluation; report: [calibration_labels.json](calibration_labels.json)):
- **Method:** Platt scaling, fitted on out-of-fold predictions and stored in each model file. `decide()` applies it.
- **ECE ≤ 0.05 in every pass and regime.**
- **Bins of 20+ rows more than 0.05 below their confidence:** none for pass 2 at 10% and 25%; one at 100%, `false` 0.8–0.9 (27 rows, said 0.86, right 0.78). Pass 1 has one at 25% and at 100%.
- **Rejected after measuring:** an isotonic map (noisier on 1,900 rows, and it cost up to 1 point of accuracy) and a two-sided Platt (no better).

**Other:**
- **Models:** gradient-boosted trees (pure Python, `arena/ml/model.py`), trained on a mix of the three regimes. Logistic regression is kept as an option.
- **Extraction:** fact precision 0.88, recall 0.85; 82% of rows extracted exactly.
- **Commands:** `python3 eval/eval_extract.py`, `python3 eval/train_model.py` (refits both model files and the report), `python3 eval/eval_hidden.py [--honest]`, `python3 -m unittest discover -s tests -p "test_engine_*.py"`.

What the evidence features capture (`arena/truth.py`, `fact_features`):
- whether the value is the one nearest in time (1% of such rows are false);
- where the date sits between two different observed values (near another value: 65% false);
- whether a never-seen value exceeds every value the fact ever had (55% false: hype).

## Limits

- **Practice is about 10% of the run's input.** Every number here is an estimate, and on the hidden rows the engine is about level with *always true* on accuracy. Its gain is the lies it catches.
- **`unsure` is never predicted** with the default policy (2% of practice; the model never finds it likelier than true or false).
- **A new value no other row states is the hard case.** It is the first page to report a change about half the time, and a lie the other half. Self-training on the input's other rows is what helps here; its gain at the run's full scale is not measured.
- **Common extraction errors:** wrong subjects from context (Android 16 vs 17 on one page), and tables written as lists ("Ads: 78%, 72%, 66%").
- **Unseen subjects and attributes:** those the practice never shows get no learned evidence. They are extracted only weakly and checked as unknown.
- **`€59 per month or €590 per year`** now reads as a choice (both values), as `value-forms.md` says; `10 GB to 20 GB` is a range at both ends.
