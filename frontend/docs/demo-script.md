# Demo script — Git Happens, Temporal Truth Engine

Target length: 2:30 (hard limit 3:00). One take, screen recording with voice.
Owner: B. Rehearse on `frontend/docs/test.csv` (or `data/test/demo.csv`, which has an answer key in
`data/test/demo_key.csv`); at 09:00, run `sample/sample.csv` live.

## Before recording

1. Pull the final `integration`, then start everything from the repository root:

   ```bash
   scripts/start.sh
   ```

   It starts the API on port 8000 and the app on **http://localhost:8080** (Vite's server, which forwards `/api` to
   the engine). Ctrl+C stops both.
2. Do NOT set `ARENA_DEMO`. Check that the pill in the sidebar says **live engine** (not "demo engine" or
   "offline"), and that the Confidence page has no "fixture · engine offline" badge. If it does, the API is not
   connected: say so in the video rather than showing fixture numbers as ours.
3. **Dry run before recording:** on **Live run**, upload `sample/sample.csv` and press **Run system** once. The API
   reads it strictly; if it rejects the file, say why on camera and show the batch runner labelling it instead:
   `ARENA_UNIVERSE=<folder with universe.csv and lexicon.json> ARENA_OUTPUT=/tmp/out .venv/bin/python -m arena.runner`.
4. Browser at 1440×900, zoom 100%, no other tabs. Open http://localhost:8080.
5. Check the predicted score (section 7) against the final measurements, and agree it with A and C.

## 0:00–0:20 — Problem, users, value

On screen: Overview.

> Companies publish claims that go out of date or were never true: a price that changed, a feature that was dropped.
> Marketing and legal reviewers, documentation teams and chatbot QA have to catch them by hand.
> We built a checker that reads each sentence, finds what our sources said on that sentence's date, and explains
> its verdict with the sentences and dates it used. It cannot invent a fact.

## 0:20–0:45 — The architecture

On screen: the **Architecture** page. Press space to play the walkthrough (arrows step back and forward).

> Every box is a technique we built and trained ourselves. A value parser and a naive Bayes model turn text into
> facts. A temporal knowledge base keeps every fact with the dates it was stated. Interval rules check a fact at the
> sentence's date, and boosted trees with Platt calibration turn that evidence into a label and a confidence. A second
> pass adds what the first pass is sure of, and in the real run a held-out control group can lower confidence where we
> are over-confident. The same evidence drives a template generator, a rule validator and an independent referee for
> our 1,000 new claims. An LLM helped us write the code; nothing in the container is a language model.

Point at: Extraction → Temporal check → Verdict, then Template generator → Validation.

## 0:45–1:20 — Live run on the sample

On screen: **Live run** → upload (file icon) `sample/sample.csv` → **Run system**.

> This is the sample the organisers released this morning: 20 rows we had never seen.

Read the real numbers on screen: the verdict counts, and open one verdict to show its reason, the facts read and the
evidence rows with their dates. Show the **Download CSV** button: the six `output.csv` columns.

## 1:20–1:45 — One sentence, two dates

On screen: **Live run** with `frontend/docs/test.csv` (upload it after the sample, **Run system**), rows `s-3` and `s-4`.

> The same sentence, "Hooly Cloud covers 8 regions", is true in August and false in January.

Open `s-3` (true), then `s-4` (false): show the reason and the evidence row with its date. The evidence is what
makes the two verdicts differ.

Rehearsal numbers (29 Oct, live engine): `s-3` true 95%, `s-4` false 65%. Re-check them before recording.

Do not demo a negated sentence ("does not cost …"): the model can override the rule there.

## 1:45–2:05 — The claims

On screen: the **Claims** page.

> Besides labelling rows, the system writes 1,000 new claims. Two independent checkers agree on every one: our
> validator, and a referee written from the published rules alone.

Filter by `change`, open one, show its JSON form and its evidence rows.

## 2:05–2:25 — How good we are

On screen: the **Confidence** page.

> A confidence should mean something: when we say 90%, we should be right about 90% of the time. We measured this on
> rows the model never learned from.

Point at, in this order:
- Labels: **87.0%** right on unseen rows, against 83.3% for always answering "true"; calibration error (ECE) **0.027**.
- Claims: date compares **133 / 133** right on rows the generator never saw; the types unseen rows cannot check are
  capped at 0.95, and we say so.
- The shift test: on subjects the model has never seen we are **below** always-"true" (79.5% vs 82.5%). Say it: knowing
  where we are weak is what self-evaluation means.
- The run-time controls: a control group the model never saw, which can only lower confidence.

Then state the prediction (section 7).

## 2:25–2:40 — Adoption

> It runs offline in one container, with no model costs, and every verdict comes with its evidence. A company swaps
> in its own pages as the universe and checks its docs, its marketing or its chatbot's answers against them.

End on the Overview.

## 7. Our predicted score

From the final measurements (STATUS.md, "Numbers"); say the caveat aloud.

- Labels right on unseen rows: about **87%** (out of fold on all 1,897 practice rows, page-grouped 5-fold; 79.5–88.8%
  across the three shift-test scenarios).
- Claims true: about **95%** (mean confidence 0.959: date compares 133/133 on unseen rows, Wilson bound 0.972; changes
  and event values capped at 0.95 because unseen rows cannot check them).
- Confidence calibrated within about ±**3** points (label ECE 0.027).
- Caveat: practice is about 10% of the final input, so these are estimates; on subjects we have never seen we expect
  to be weaker.

## Checklist

- [ ] "live engine" pill, no "fixture · engine offline" badge.
- [ ] Diagram, live sample run, evidence for a verdict, the claims, the confidence page: all shown.
- [ ] Problem, users, value, adoption: all said.
- [ ] Predicted score stated, with how it was measured, and the weak spot (new subjects).
- [ ] Under 3:00.
