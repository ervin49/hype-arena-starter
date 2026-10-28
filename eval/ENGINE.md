# How the engine labels a sentence

*Section for the README (C pastes it). Owner: A. Numbers: `eval/README.md`.*

The engine decides whether a sentence about Hooly is true on its date. It has five stages. Each is a small, inspectable component that learns only from the practice data, and none of them is a language model.

| Stage | File | Technique | What it learns from practice |
|---|---|---|---|
| 1. Value parser | `arena/values.py` | Rules: the referee's `value-forms.md`, implemented exactly | Nothing; it is a specification |
| 2. Name matcher | `arena/lexicon.py` | Longest-first matching of the lexicon's names and aliases | Nothing; it is the lexicon |
| 3. Fact extraction | `arena/extract.py` | Naive Bayes over the words around each value, with page context | Which attribute a value belongs to, and when a number is no fact |
| 4. Temporal knowledge base | `arena/truth.py` | Each fact's history; evidence features at the sentence's date | Facts with dates, from true and false rows |
| 5. Verdict | `arena/ml/model.py` | Gradient-boosted trees, Platt calibration, one round of self-training | How evidence patterns relate to true and false |

## The stages

1. **Value parser.** It reads every price, percentage, date, version, duration and quantity exactly as the referee does: units convert, and approximations, ranges and negated values read as nothing. On the practice forms it finds every value except names and yes or no, which the extractor handles.
2. **Name matcher.** It finds subjects by name or alias, longest first, so *Hooly AI Pro* names the plan, not the company.
3. **Fact extraction.** Each value becomes a candidate fact. A naive Bayes model picks its subject and attribute from the words around it, constrained by the value's kind and unit. A sentence that names no subject (*"It costs €59 a month"*) takes one from the rows before it on the same page.
4. **Temporal knowledge base.** Prices, versions and headcounts change over time, so every fact keeps its history. A claim is checked against what the evidence says *on the sentence's date*. The checks include:
   - whether the value is the one nearest in time;
   - whether the date falls near a change of value;
   - whether a value never seen before exceeds everything the fact ever had, which is how hype looks.

   Rows labelled false are negative evidence.
5. **Verdict.** Gradient-boosted trees weigh the evidence and output a probability. Platt scaling then maps it to how often such rows were really right, out of fold, so a confidence of 0.9 means right about 90% of the time.

   Then comes one round of **self-training**. Every row of the input is labelled once; the confident labels join the evidence; every row is labelled again. A row's own page and copies of its sentence never count for it, so nothing confirms itself.

Every verdict carries its reason and the ids of the rows it rests on.

## Why there is no LLM

- **The rules:** the system may not be an LLM.
- **The task:** the universe contradicts the real world on purpose. A pretrained model would bring facts the universe does not hold.
- **The data:** 1,900 labelled sentences are enough for small models and too few for large ones. Our measurements show the limit is missing evidence, not model capacity: with perfect extraction, accuracy rises by only about 4 points.
- **The practice:** small models are fast (two passes over 20,000 rows in about 40 seconds on a laptop), run offline, and explain every answer.

## How good it is, and how we know

Every number is measured on practice rows the engine did not learn from, with whole pages held out at a time:

- **Hidden rows (`scripts/check.sh`'s setup), with the models retrained without them:** 329 of 380 right (86.6%). *Always true* scores 331. The engine catches 22 of the 49 false sentences, and 22 of the 39 it calls false are false.
- **Calibration:** expected calibration error (ECE) 0.037 on those hidden rows. Across the folds it is 0.022–0.033, with no confidence bin of 20 or more rows more than 0.05 below its stated confidence.
- **Scale:** practice is about 10% of the final input, so these are estimates. More evidence helps in every test we ran.
