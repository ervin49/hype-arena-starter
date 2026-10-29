# Git Happens — status

**Last updated:** 2026-10-28 16:30 EET, by C, after merging `dev/a`, `dev/b` and `dev/c` into `integration`
**Deadline:** PR to QA-DNA open before **11:00 on 29 Oct**. Sample released at 09:00. The plan is in `PLAN_NEXT.md`.

> Updated on every merge into `integration`. If something here is out of date, tell C.

## At a glance

| Part | Owner | State |
|---|---|---|
| Engine: extraction, temporal check, ML verdict | A | ✅ boosted trees, self-training, change-timing features; one batch with page context |
| Frontend: upload, verdicts, claims, architecture replay, confidence | B | ✅ works with the real engine; Next.js 15.5.28 (patched) |
| API: `/health`, `/predict`, `/predict/csv`, `/claims`, `/metrics` | C | ✅ works; uploads labelled like the batch run |
| Batch runner → `/output/output.csv` | C | ✅ A's batch (`label_rows`); passes the official format checker locally |
| Claim generator + validator: 1,000 claims | C | ✅ 1,000 valid; confidence checked on unseen rows (strict backtest); pool ~1,300 |
| Confidence page (`/metrics` → `/confidence`) | B, C | ✅ labels; claims only where unseen rows check them; shift-test table; run-time controls |
| Label calibration (`eval/calibration_labels.json`) | A | ✅ Platt, cross-fitted; ECE 0.027 |
| Demo script (`frontend/docs/demo-script.md`) | B | ✅ draft |
| `Dockerfile` + `scripts/check.sh` in Docker | C | ✅ `scripts/check.sh` passes (exit 0, 380/380 labelled, 1,000 claims); a **synthetic** 20,000-row input (made by us, not the organisers' data) runs in 131 s with the controls; image ~50 MB |
| Run-time controls (`arena/controls.py`) | C | ✅ confidence control on a held-out group, distribution monitor, claim veto from confident input rows; claim confidence lowered by the veto share |
| ML experiments, measured and **not** in the run | A, B, C | 5-model ensemble (A), synthetic lies (B), confidence model / layer 3 (C): see "Experiments" |
| README: how it works, start guide, predicted score | C | ⏸ not now |
| Video on the 20 sample rows | all | ⏳ 29 Oct, 09:00 |
| Pull request to QA-DNA | C | ⏳ 29 Oct, before 11:00 |

## Numbers (practice data, every fifth label hidden, as `check.sh` does)

| Metric | Value |
|---|---|
| Hidden rows labelled right | **340 / 380** (89.5%); 331 before this merge, 329 this morning; always `true` would score 85% |
| False sentences caught | **27 of 49** (22 before, 9 this morning); true rows called false: 11 (15 before) |
| Answers at confidence 0.9+ | 196, 96% right |
| Labels, honest (A, out of fold, `eval/train_model.py`) | accuracy **87.0%** (always `true`: 83.3%); lies caught 118 / 277; ECE 0.027 |
| Labels on unseen rows given all other practice evidence (`scripts/train_confidence.py`) | 88.7% of 1,858; lies 143 / 277; ECE 0.044 |
| Weakest band | `false` at 0.5–0.8: about 57% right; `true` at 0.5–0.6: 65% right |
| `unsure` predicted | never (A's default; a team decision once scoring is known) |
| Claims | 1,000: 430 compare (dates), 317 change, 247 at_event (at most 60 per event), 4 fact (dates), 2 relation |
| Claim confidence | measured on unseen rows: 430 at 0.972, 564 at 0.95 (capped), 4 at 0.867, 2 at 0.80; mean 0.959 |
| Full run time | ~11 s on practice with the controls; 131 s on our **synthetic** 20,000-row input (of 30 min) |
| Tests | 394 Python tests pass (206 of them every example of `claim-forms.md` and `value-forms.md`) (`.venv/bin/pytest -q`); frontend type-checks, lints and builds; all 4 pages and 5 API routes checked live |

### Claim backtest (`scripts/backtest_claims.py` → `reports/claims_calibration.json`)

Claims built from the practice rows before 1 May, 1 Jul and 1 Sep, then judged twice:
- **full judge**: all practice rows. Partly circular, because the rows a claim came from also judge it.
- **strict judge**: only the rows dated after the cut-off, which the generator never saw.

Confidence is the lower of the two Wilson lower bounds (95%). If the strict judge can't check a group, its confidence is capped at 0.95.

| Group | Full judge | Strict judge | Decision | Confidence |
|---|---|---|---|---|
| compare (dates) | 1,314/1,314 | 133/133 | kept | 0.972 |
| at_event | 449/449 | can't check | kept, capped | 0.95 |
| change | 350/350 | can't check | kept, capped | 0.95 |
| fact (dates) | 62/62 | 25/25 | kept | 0.867 |
| fact (values that never changed) | 59/113 | 59/113 | dropped | — |
| fact (values that changed before) | 36/51 | 36/51 | dropped | — |
| compare (amounts) | 28/29 | 28/29 | dropped (bar: 98% at every cut-off) | — |
| relation | not judged | not judged | kept, cautious | 0.80 |

Why it isn't 0.99: the earlier 0.99 came from the full judge alone, which grades a claim with the rows it was built from. Self-evaluation scores honest confidence, so we now ship only what the unseen rows support. The final input is ~10× larger.

### Run-time controls (`arena/controls.py`)

The run can't be adjusted after the freeze, so the system checks itself on the real input:

| Control | How | On practice (`check.sh`) | On our synthetic 20,000-row input |
|---|---|---|---|
| Confidence | A control model (`scripts/train_control.py`) never saw 381 practice rows. In the run it labels them in the context of the real input. Confidence becomes 0.5 + k·(c − 0.5), with k fitted per label on that group: it can only go down. | 298 answers, 86.9% right, said 0.83: k = 1 (nothing lowered) | 369 answers, 84% right; `false` over-stated, so k = 0.6; ECE 0.046 → 0.035 |
| Distribution | The share of `false` on the input against the control group, logged | 10.0% vs 8.4% | 17.0% vs 14.1% |
| Claims | Input rows labelled `true` at ≥ 0.9 are added as evidence; a candidate they contradict is vetoed and replaced from the reserve. A group that loses a share v of its candidates gets confidence c × (1 − v); a vetoed claim used only to fill the 1,000 gets 0.5 | 197 rows, 0 vetoed, confidence unchanged | 10,582 rows, 9 vetoed: at_event 0.95 → 0.932, change 0.95 → 0.947, date compares 0.971 |

**The 20,000-row input is synthetic, made by us:** the 1,897 practice rows plus 18,103 copies of practice sentences with new ids, dates shifted by up to ±60 days and empty labels. We do not have the organisers' 18,000 rows. It tests speed, limits and that the controls react to noise; it says nothing about our accuracy on new text, and its 150 vetoes and factor 0.6 react to our artificial noise, not to the real data.

### Shift test (`scripts/shift_test.py` → `reports/shift_test.json`)

Does confidence stay honest when the run's rows differ from practice? In each scenario, ~20% of the practice data is "unseen". The main and control models are trained only on the rest, then the run is replayed with the control.

| Scenario (unseen part) | Right | Always `true` | Said → after control | ECE → after | Brier → after |
|---|---|---|---|---|---|
| Random pages (no shift) | 88.8% | 83.9% | 0.826 → 0.826 | 0.062 → 0.062 | 0.093 → 0.093 |
| Latest pages (time shift) | 83.5% | 81.5% | 0.826 → 0.826 | 0.034 → 0.034 | 0.120 → 0.120 |
| Held-out subjects (new products) | **79.5%** | **82.5%** | 0.835 → 0.826 | 0.040 → **0.031** | 0.144 → 0.140 |

- Confidence stays within ~2 points of the truth in every scenario. Where it was over-stated (new subjects), the control lowered `false` (factor 0.52) and the calibration error dropped from 0.040 to 0.031. On random pages we are now modest (said 0.83, right 88.8%): the control never raises confidence.
- **On subjects it has never seen, the engine is worse than answering `true` (79.5% vs 82.5%).** That's a correctness problem for A, not a confidence one.

### Experiments, measured and not in the run

| Experiment | Owner | Result | Decision |
|---|---|---|---|
| 5-model ensemble as the answerer (`eval/train_ensemble.py`) | A | Out of fold: lies 143 → 114, ECE 0.045 → 0.058; latest pages 83.5 → 82.0% | Not the default. Its `spread` flags wrong answers (about 2× higher on them, AUC 0.80) |
| Synthetic lies (`eval/augment.py`) | B | Lies caught 118 → 104 at 1×; 5 of 6 shift cells worse | Not used |
| Confidence model, layer 3 (`arena/confidence.py`) | C | Out of fold ECE 0.044 → 0.005, Brier 0.0887 → 0.0856. With the control (`reports/shift_test_layer3.json`): random pages 0.062 → **0.016**, but latest pages 0.034 → **0.055** and new subjects 0.031 → **0.083** (over-confident whenever the data shifts) | Not in the run; round 3 tries a shift-proof version |
| Layer 3's flip (`false` → `true` when unlikely right) | C | +5 rows of accuracy, −16 lies caught | Not used |

## Branches

```
dev/a (A) ─┐
dev/b (B) ─┼──► integration (C merges and tests) ──► main ──► PR to QA-DNA
dev/c (C) ─┘
```

- Each person pushes only their own `dev/` branch and says so in the chat; C merges into `integration`.
- After every merge, everyone runs `git merge origin/integration` into their branch.
- Anyone can pull `integration` to run the whole system.
- `main` is updated once, at the freeze.
- The first-phase branches (`ML-and-python`, `team/frontend`, `teamapi`) are kept as a record; nobody works on them. Details: `PLAN_NEXT.md`, section 8.

## How to run it

```sh
# once
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
cd frontend && npm ci && echo "ARENA_API_URL=http://127.0.0.1:8000" > .env.local && cd ..

# terminal 1: API with the real engine (builds the 1,000 claims at startup, ~1 s)
.venv/bin/uvicorn api.main:app --port 8000

# terminal 2: frontend on http://localhost:3000
cd frontend && npm run dev        # or: npm run build && npm start (no dev button, for the video)
```

The batch run, as the judges run it, on the practice data:

```sh
mkdir -p /tmp/arena/universe /tmp/arena/output
python3 scripts/input.py data/practice.csv /tmp/arena/universe/universe.csv
cp data/lexicon.json /tmp/arena/universe/
ARENA_UNIVERSE=/tmp/arena/universe ARENA_OUTPUT=/tmp/arena/output .venv/bin/python -m arena.runner
python3 scripts/check_output.py /tmp/arena/output data/practice.csv /tmp/arena/universe/universe.csv
```

## Next, by owner (round 3, prompts in PLAN_FINAL.md)

Where the errors are (1,858 honest answers, `reports/confidence_oof.json`): ~145 of ~210 errors are rows where our evidence **contradicts** the sentence. In the largest case, `stable_mismatch`, 151 of 210 rows are actually true. In all, **375 true rows** have a contradicting check.

First look at those 375 (C, 12 read by hand), two different causes:
- **Real changes over time, with the evidence only on the other side of the change** (most of the sample): "Hooly Docs grows to 80 templates" (Aug) vs "30 templates" (Jan–Mar); "75 editors" (Aug) vs "40 editors" (Mar); Pixel 10 "95,000 phones sold" (Jun) vs "410,000" (Oct); Calendar "v1.0" (Mar) vs "1.4" (Sep). A count, version or total that **grows** is not contradicted by an older smaller or a later larger value. Words like "grows to", "now", "has sold" mark the change.
- **Wrong fact read**: "…said Richard Hendrix, our CTO" read as *Hooly Jules lead* (it is Hooly's CTO); "Released on 22 September 2026" assigned to Hooly Chrome (gold: Hooly Android 17); "Stable is planned for 8 September 2026" assigned to Hooly Pixel Fold (gold: Hooly Android 17). The subject taken from context is wrong.

To list them again: load `reports/confidence_oof.json` (records with `gold` and the full `prediction`), keep `gold == "true"` and `prediction.kind == "contradicted"`, and print each check whose `case` contains `mismatch`, with its `fact` and `evidence_ids`.

| # | What | Who |
|---|---|---|
| 1 | Fix false contradictions: classify the true `stable_mismatch` rows by cause, fix the biggest | A |
| 2 | XGBoost / LightGBM on the same features, then monotonic constraints; export to JSON trees if it wins | B |
| 3 | Text signal for lies: does the wording of a sentence predict a lie, out of fold? | B |
| 4 | Layer 3, shift-proof: trained on subject/time-held-out folds, with A's `spread` | C |
| 5 | "Not understood" rows (83 answers, 14 errors): extraction coverage | A, after 1 |
| 6 | `unsure` policy, once the organisers say how wrong answers score | C |

**Team**
- Ask the organisers how confidence, wrong answers and `unsure` are scored.
- Freeze: start guide (location to decide), clean-up (`test.csv`, `.claude/launch.json`), `integration` → `main`, PR "Git Happens" before 11:00 on 29 Oct.

## Known risks

- Practice is ~10% of the final input: new facts and later value changes we cannot see.
- Claims now avoid values that can go stale (the backtest showed 52–71% right for them) and dates that move (`latest_*`, `next_*`, `planned_*`, `*_since`); the 1,000 are one-time dates, changes and event values.
- at_event and change claims can't be checked on unseen rows, so their 0.95 is a cap, not a measurement.
- Up to 40 date compares (30 claims of other types) rest on one fact; if a fact in our data is wrong, its claims fail together. Every event date comes from rows labelled true.
- The local `check.sh` label count (340/380) is an upper bound: the image's model was trained on all practice rows. The honest figure is 87.0% out of fold, against 83.3% for always `true`.
- On subjects it never saw, the engine is below always `true` (79.5% vs 82.5%, shift test).

## Log

| When | What |
|---|---|
| 29 Oct | C: an **Excel** download next to each CSV download (dashboard and claims page). Spreadsheets set to a European region read `0.971` as 971 and split on `;`, so this file uses semicolons, decimal commas and a byte-order mark. The plain CSV stays the official format, byte-identical to `output.csv`. |
| 29 Oct | **Engine work closed.** Merged A's two guards: negated values ("does not cost €59" inverts its check and never counts as evidence) and approximations ("roughly 50,000 users" keeps its value, with an `approx` issue), as the forms read them. Practice has no such facts, so every number is identical: out of fold 0.870, lies 118/277, ECE 0.027; shift test 88.8 / 83.5 / 79.5; density test 338/380; `check.sh` 340/380, 1,000 claims. Models unchanged, so the control model needs no retraining. **Tried and rejected** (A): span and neighbour features (0.868–0.869; the model already has the information); fallback-subject and lost-clause guards (no signal in the audit). **Screened by C on the out-of-fold answers:** speaker rows ("Gavin:") 16.5% false vs 14.5%, no signal. **`unsure`:** every rule loses right answers (no evidence −64, confidence < 0.55 −46, < 0.60 −96). The 39 gold `unsure` rows look like ordinary rows (most have evidence and confidence 0.8–0.95), and the engine's own `unsure` probability is a constant 0.02. So we never answer `unsure`, unless the organisers say a wrong answer costs ≥ 1.5× what a right one earns; then `ARENA_UNSURE_BELOW=0.55`. 621 tests. |
| 29 Oct | **A:** 3.1 (stable_mismatch only inside the span) and 3.6 were tried and **rejected**. The rule does what the plan says on gold forms (n=127 at 38% false → n=22 at 95% false), but the trained model gets worse (out of fold 0.870 → 0.866, lies 118 → 113, ECE 0.027 → 0.030). The model trains on extracted forms with 10–100% of pages labelled, where the wide rule still carries signal. A moves to 3.3 (extraction guards). To re-test on the density test if lies caught fall there. **B merged:** `scripts/referee.py`, an independent referee of the claims written from `contracts/` only. It accepts every official example, rejects 6,721 of 6,724 broken claims, and **rejects 0 of our 1,000**. Also `scripts/synth_universe.py`, density test v2 (16,403 rows): hidden rows 340 → 338/380, lies 33 → 34/49, control factors 1.0, 69 s, 233 MiB, so the dense input causes no collapse. Hand audit of 50 claims: all right. **C:** wording. 58 of the 247 at_event claims read "Hooly Photos had 64,000,000 monthly active users at the time of …" (value-forms allows two words between a number and its noun). Possessives read "Hooly Docs' launch", and SDKs/IDEs are capitalised. Our validator and the referee both pass all 1,000; `check.sh` passes; 615 tests. |
| 29 Oct | C: claims mix moved toward what unseen rows can check (PLAN_ENGINE.md 4.2–4.4). **Event dates:** all five come from rows labelled true, read with their gold forms; I/O 2026 and the May outage have 3 reports after the event, Cloud Next 1 plus 3 plans agreeing; Maps Day and Gemini Launch Night have 1 each, so no date is in doubt. **Mix:** at most 60 claims per event (was 100), keeping the ones whose bracketing reports are closest (the `open_roles` ones drop out by themselves); up to 40 date compares per fact. Now 430 date compares (was 294), 247 at_event (was 383), 317 change. Date compares re-measured 133/133 on unseen rows: 0.972. **Wording:** "Hooly had 38 employees at the time of …" instead of "Hooly employees was 38 employees …" (31 claims). Labels unchanged; `check.sh` passes, 398 tests. |
| 29 Oct | Plan for the night after the organisers mapped the rubric (claims 30%, labels 15%): `PLAN_ENGINE.md`, with a prompt each for A, B and C. **A:** stable_mismatch only inside the span (inside 90% false, outside 74% true), then plans versus realised dates and extraction guards. **B:** an independent referee of the 1,000 claims, written from the spec without reading our validator, then a denser synthetic test. **C:** claims mix and grammar, merges. `scripts/rule_audit.py` added; it reproduces the plan's tables. |
| 29 Oct | C: the results can be downloaded as CSV from the frontend. On the dashboard, **Download CSV** saves every checked row, and on the claims page it saves all 1,000 claims. Both use the six `output.csv` columns, written byte for byte as `arena/io.py` writes them (checked against it on the 1,000 claims). Frontend only; the run is unchanged. |
| 28 Oct, night | Team chose a focused round 3 (8 hours left): A fixes false contradictions, B tests XGBoost/LightGBM and a text signal once, C keeps the run safe and merges only what measures better. C's first look at the 375 true-but-contradicted rows: most are real changes over time (growing counts, versions, totals) judged against evidence from the other side of the change; some are a wrong subject or attribute taken from context. Layer 3's full shift record: new subjects 0.031 → 0.083 with it, so it stays out. |
| 28 Oct, night | C: layer 3, a confidence model on the engine's answers (`arena/confidence.py`, `scripts/train_confidence.py`; `scripts/shift_test.py --layer3`). Out of fold it calibrates far better, but it is over-confident when the data shifts, even with the run-time control, so it is **not in the run**. Error analysis: ~145 of ~210 errors are rows where our evidence contradicts the sentence; 151 of the 210 `stable_mismatch` rows are actually true. Round 3 planned on that. 394 tests pass; the run is unchanged. |
| 28 Oct, night | Merged ML round 2, both measured and both **not used as the default**. **A, 5-model ensemble** (`eval/train_ensemble.py`, `label_rows(..., ensemble=True)`): as the answerer it catches fewer lies (143 → 114 of 277 out of fold) and is not better on the shift test, so the single model stays. Its `spread` (how much the 5 disagree) flags wrong answers: about twice as high on them, AUC 0.80. **B, synthetic lies** (`eval/augment.py`, `scripts/train_augmented.py`): lies caught fall as the synthetic share rises (118 → 104 at 1×), and 5 of 6 shift cells are worse, so it is not used: more lies of the same kind add no evidence. The run is unchanged: `check.sh` 340/380, 1,000 claims; 391 tests pass. |
| 28 Oct, night | Merged A's `dev/a` (rare attributes read, subject origin as a feature; models and control retrained): out of fold 0.863 → **0.870**, lies caught 110 → **118**/277; hidden rows 337 → 339/380, lies 27 → 31/49. Shift test confirmed by C: random 88.0 → 88.8%, latest 83.7 → 83.5%, new subjects 80.3 → 79.5% (still below always `true`). C did B's confidence-page tasks: the claims chart shows only types checked on unseen rows (the rest listed as capped), a shift-test table and a run-time controls card, from `/metrics`. |
| 28 Oct, night | C: claim-confidence control. A group that the input's confident rows contradict loses confidence in proportion (c × (1 − v)); a vetoed claim used only to fill the 1,000 gets 0.5. No change on practice; on the synthetic 20,000-row input, 9 vetoes lower at_event to 0.932 and change to 0.947. 387 tests pass. |
| 28 Oct, night | C: every example of `claim-forms.md` and `value-forms.md` is now a test (206), read from the files. The validator was fixed to match all of them: a second sentence may say anything, `on the same day as` counts as one phrase, `…, up from …` / `down from` read, and `up`/`down` must match the values. The 1,000 claims are unchanged. `/metrics` serves `shift` (with the always-`true` baseline) and `controls` (`reports/controls.json`, from `scripts/train_control.py`). Shift test rerun for the current engine. 384 tests pass. |
| 28 Oct, night | C merged B's `fix/overfitting` engine (regularized trees, `l2=10, min_hess=20`) into `dev/c`: better in all three shift-test scenarios (random 87.7 → 88.0%, latest 83.3 → 83.7%, new subjects 79.5 → 80.3%; ECE same or lower) and on the honest hidden rows (329 → 337/380). Its claim formula (Laplace, date compares 0.99) was **not** taken: claim confidence stays the cautious Wilson bound. Control model retrained; control-group ECE 0.039 → 0.031. 178 tests, `check.sh` pass. |
| 28 Oct, evening | C: run-time controls, as the organisers asked. A held-out control group recalibrates confidence on the real input (it can only lower it), a distribution monitor, and a claim veto from the input rows the engine is sure of. `check.sh` passes; our synthetic 20,000-row input in 131 s; 178 tests pass. |
| 28 Oct, evening | C: `Dockerfile` (python 3.12 slim, `jsonschema` only, `USER 10001`). `scripts/check.sh` passes in Docker. A synthetic 20,000-row input made by us (practice sentences copied with shifted dates; 18,103 unlabelled) under the judges' limits (offline, read-only, 2 CPUs, 6 GiB) runs in 63 s; output 0.67 MB. |
| 28 Oct, evening | C: claim confidence made honest. Moving dates (`latest_release_date` etc.) dropped after a strict check found a stale claim. The backtest now has a strict judge (unseen rows only); confidence is the lower bound of both judges and capped at 0.95 where the strict judge can't check. 993 claims at 0.99 became 294 at 0.971 and 700 at 0.95. 169 tests pass. |
| 28 Oct, 16:30 | Merged `dev/a` (engine: boosted trees, self-training, label calibration), `dev/b` (confidence page, Next.js 15.5.28, demo script), `dev/c`; no conflicts. 340/380 right, false caught 27/49; 167 tests pass; claim backtest unchanged; C fixed `/metrics` to the agreed shape (`n`, shipped groups only). After pulling, run `npm ci` in `frontend/`. |
| 28 Oct, 15:55 | `dev/c` (local): claim backtest and measured confidence (993 claims at 0.99; stale `fact` groups dropped); runner and API use A's `label_rows` (331/380 right, false caught 9 → 22); `GET /metrics`. |
| 28 Oct, 15:10 | Claim generator + validator: 1,000 valid claims; runner passes the official format checker. API: `/claims` and evidence texts. Frontend: Claims page, claim steps in the replay, evidence sentences in the detail panel. |
| 28 Oct, ~13:15 | Engine merged into `integration`; first live run with the real engine (4-row demo). |
| 28 Oct, ~12:00 | API and frontend merged into `integration`; contract checked field by field. |
