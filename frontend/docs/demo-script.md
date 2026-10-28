# Demo script — Git Happens, Temporal Truth Engine

Target length: 2:30 (hard limit 3:00). One take, screen recording with voice.
Owner: B. Rehearse on `test.csv`; on Thursday, run `sample/sample.csv` live.

## Before recording

1. Pull the final `integration`, then start both servers from it:

   ```bash
   .venv/bin/uvicorn api.main:app --port 8000
   ```

   ```bash
   cd frontend && npm ci && npm run build && ARENA_API_URL=http://127.0.0.1:8000 npm start
   ```

   Record from `npm start`, never `npm run dev` (it shows the dev indicator).
2. Do NOT set `ARENA_DEMO` or `ARENA_METRICS_FIXTURE`. Check that the top-right pill says **Live engine**, and that
   the Confidence page has no "Simulated measurements" banner. If it does, C's `/metrics` is not connected yet: say so
   in the video rather than showing fixture numbers as ours.
3. Browser at 1440×900, zoom 100%, light theme, no other tabs. Open http://localhost:3000.
4. Fill in the predicted score (section 7) from the final measurements, and agree it with A and C.
5. Open a new private window, or clear the site data, so the Architecture tab has no leftover run.

## 0:00–0:20 — Problem, users, value

On screen: the dashboard, empty.

> Companies publish claims that go out of date or were never true: a price that changed, a feature that was dropped.
> Marketing and legal reviewers, documentation teams and chatbot QA have to catch them by hand.
> We built a checker that reads each sentence, finds what our sources said on that sentence's date, and explains
> its verdict. It cannot invent facts, because there is no language model inside it.

## 0:20–0:45 — The architecture

On screen: the Architecture tab (no run yet: the dimmed diagram).

> Every box is a technique we built and trained ourselves. A value parser and a naive Bayes model turn text into facts.
> A temporal knowledge base keeps every fact with the dates it was stated. Interval rules check a fact at a sentence's
> date, and a logistic regression turns that evidence into a label and a confidence. The same evidence base drives
> a template generator and a rule validator that write our 1,000 new claims.

Point at: Extraction → Temporal check → Verdict, then Template generator → Validation.

## 0:45–1:20 — Live run on the sample

On screen: Architecture tab → **Run a CSV** → `sample/sample.csv`.

> This is the sample the organisers released this morning: 20 rows we had never seen.

Let the replay play from the left; read the real numbers from the boxes as they appear (rows to check, facts found,
evidence citations, the verdict counts, the answer time).

Then: Dashboard. Show the KPI cards and the verdicts table.

## 1:20–1:45 — One sentence, two dates

On screen: the dashboard with `test.csv` loaded (upload it after the sample), rows `s-3` and `s-4`.

> The same sentence, "Hooly Cloud covers 8 regions", is true in August and false in January.

Click `s-3` (true), then `s-4` (false). In the detail panel show the gauge, the reason, the extracted fact, and the
evidence rows with their dates: the evidence is what makes the two verdicts differ.

Rehearsal numbers (28 Oct, live engine): `s-3` true 94%, `s-4` false 65%. Re-check them before recording.

## 1:45–2:05 — The claims

On screen: the Claims tab.

> Besides labelling rows, the system writes 1,000 new claims, each true by our evidence.

Filter by `change`, click one, show its JSON form and its evidence rows.

## 2:05–2:25 — How good we are

On screen: the Confidence tab.

> A confidence should mean something: when we say 90%, we should be right about 90% of the time. We measured this on
> rows the model never learned from, and on claims built before a cut-off date and checked after it.

Point at one calibrated band and at the claim types. Then state the prediction (section 7).

## 2:25–2:40 — Adoption

> It runs offline on a laptop, in one container, with no model costs, and every verdict comes with its evidence.

End on the dashboard.

## 7. Our predicted score (fill in before recording)

Write it from the final run's measurements, the same numbers as in the README:

- Labels right on unseen rows: about **__%** (measured: __ / __ on the hidden practice rows, __-fold cross-validation).
- Claims true: about **__%** (backtest: __ / __ at __ cut-offs).
- Confidence calibrated within ±**__** points (label ECE __).
- Caveat to say aloud: practice is about 10% of the final input, so these are estimates.

## Checklist

- [ ] Live engine pill, no simulated banner, no dev indicator.
- [ ] Diagram, live sample run, evidence for a verdict, the claims, the confidence chart: all shown.
- [ ] Problem, users, value, adoption: all said.
- [ ] Predicted score stated, with how it was measured.
- [ ] Under 3:00.
