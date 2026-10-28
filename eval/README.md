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
- `arena/ml/model.json` must be in the image. Without it, `classify` falls back to the rules alone, which are much worse (below).
- Time: about 25 s and under 100 MB for 20,000 rows on a laptop.
- `ARENA_UNSURE_BELOW` (env, default `0`): a firm label whose probability is below it is exported as `unsure`. `0` keeps every label firm. This is a team decision once the scoring is known.

Export: `label` and `confidence` (`None` → empty cell). Everything else is for display.

## What a prediction holds (B: display)

```json
{"id": "...", "label": "true", "confidence": 0.92, "evidence_ids": ["p-1755", "..."],
 "reason": "Supported: Hooly AI Pro price: last stated so on 2026-10-07.",
 "probs": {"true": 0.92, "false": 0.054, "unsure": 0.026},
 "checks": [{"fact": "Hooly AI Pro price = EUR 59/month", "status": "supported", "case": "after_last_match", "...": "..."}],
 "extraction": {"facts": [...], "complete": true, "issues": [], "scores": [7.1]}}
```

`evidence_ids` are practice row ids, which the UI can show as sources. `checks[].features` is diagnostic only.

## Results (page-grouped 5-fold cross-validation; a held-out page gives nothing to the base, the extractor or the model)

| | accuracy | false recall | false precision |
|---|---|---|---|
| always `true` | 0.833 | 0 | n/a |
| rules only | 0.53 | 0.73 | 0.28 |
| **model (shipped)** | **0.848** | **0.30** | **0.59** |
| model with gold forms (ceiling of the checker) | 0.886 | 0.57 | 0.73 |

- Calibration: labels at confidence 0.9+ are right 95.5% of the time, 0.8+ 85%, 0.7+ 78%.
- Extraction: fact precision 0.85, recall 0.79; 75% of rows extracted exactly; value parsing reads every value of the practice forms (names and yes or no aside).
- Run: `python3 eval/eval_extract.py`, `python3 eval/train_model.py` (also refits `arena/ml/model.json`), `python3 -m unittest discover -s tests -p "test_engine_*.py"`.

## Limits

- Practice is about 10% of the run's input. Practice rows hidden by `scripts/check.sh` are already in the image's base, so the checker's label count there is an optimistic upper bound. The table above is the honest estimate.
- `unsure` is never predicted with the default policy (2% of practice; the model never finds it likelier than true or false).
- A new value no other row states is the hard case. It is the first page to report a change about half the time, and a lie the other half. Corroboration from the input's other rows helps, and more rows at runtime should help more, but this is not measured.
- Wrong subjects from context (Android 16 vs 17 on one page) and tables written as lists ("Ads: 78%, 72%, 66%") are the commonest extraction errors.
- Subjects or attributes the practice never shows get no learned evidence. They are extracted only weakly and checked as unknown.
