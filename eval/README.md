# Engine (A): how to call it, what it scores, where it is weak

Branch `ML-and-python`. Python 3.12, standard library only: nothing to add to `requirements.txt`.

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

**Use this for the batch run instead:** it does the same, plus page context and corroboration across the whole input:

```python
from arena.classify import label_rows
predictions = label_rows(universe_rows, practice_rows, lexicon)   # universe in input order
# -> one prediction per row with an empty label; labelled rows are skipped
```

- `universe_rows`: `/universe/universe.csv` as read, **in file order**. Labelled rows are kept: they give context ("It costs €59 a month" takes its subject from the rows before it on the same page) and corroboration.
- `practice_rows`: `data/practice.csv` copied into the image, with `form`. The runtime input has no `form`.
- `arena/ml/model.json` and `arena/ml/model_pass2.json` must be in the image. Without the first, `classify` falls back to the rules alone, which are much worse (below).
- `label_rows` **self-trains**: a second pass re-checks every row against the evidence plus the rows the first pass is confident about (P ≥ 0.85), leaving out each row's own page. Only `label_rows` does this. Calling `classify` row by row gives pass 1 only.
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

## Results (page-grouped 5-fold cross-validation; a held-out page gives nothing to the base, the extractor or the models)

The run has about 10% labelled evidence (1,900 practice rows) and 90% unlabelled text. `eval/train_model.py` simulates that by making only a fraction of the other pages labelled evidence:

| Labelled evidence | Pass 1 | Pass 2, self-trained | False recall, pass 1 → 2 |
|---|---|---|---|
| 10% (the run's ratio) | 0.831 | **0.840** | 0.09 → 0.22 |
| 25% | 0.840 | **0.848** | 0.20 → 0.29 |
| 100% (dense evidence, as in the live demo) | 0.866 | **0.868** | 0.39 → 0.43 |

"Always true" scores 0.833. The simulated regimes have far less evidence than the run (a few hundred labelled rows instead of 1,900, and 1,900 unlabelled rows instead of 18,000), so their absolute numbers are pessimistic; the gain from self-training is the signal.

- Models: gradient-boosted trees (pure Python, `arena/ml/model.py`), trained on a mix of the three regimes. Logistic regression is kept as an option.
- Calibration: labels at confidence 0.9+ are right about 95% of the time.
- Extraction: fact precision 0.85, recall 0.79; 75% of rows extracted exactly.
- Run: `python3 eval/eval_extract.py`, `python3 eval/train_model.py` (refits both model files), `python3 -m unittest discover -s tests -p "test_engine_*.py"`.

What the evidence features capture (`arena/truth.py`, `fact_features`): whether the value is the one nearest in time (1% of such rows are false), where the date sits between two different observed values (near another value: 65% false), and whether a never-seen value exceeds every value the fact ever had (55% false: hype).

## Limits

- Practice is about 10% of the run's input. Practice rows hidden by `scripts/check.sh` are already in the image's base, so the checker's label count there is an optimistic upper bound. The table above is the honest estimate.
- `unsure` is never predicted with the default policy (2% of practice; the model never finds it likelier than true or false).
- A new value no other row states is the hard case. It is the first page to report a change about half the time, and a lie the other half. Self-training on the input's other rows is what helps here; its gain at the run's full scale is not measured.
- Wrong subjects from context (Android 16 vs 17 on one page) and tables written as lists ("Ads: 78%, 72%, 66%") are the commonest extraction errors.
- Subjects or attributes the practice never shows get no learned evidence. They are extracted only weakly and checked as unknown.
