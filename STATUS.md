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
| Confidence chart (`/metrics` → `/confidence` page) | B | ✅ real measured numbers, labels and claims |
| Label calibration (`eval/calibration_labels.json`) | A | ✅ Platt, cross-fitted; ECE 0.027 |
| Demo script (`frontend/docs/demo-script.md`) | B | ✅ draft |
| `Dockerfile` + `scripts/check.sh` in Docker | C | ✅ `scripts/check.sh` passes (exit 0, 380/380 labelled, 1,000 claims); a **synthetic** 20,000-row input (made by us, not the organisers' data) runs in 131 s with the controls; image ~50 MB |
| Run-time controls (`arena/controls.py`) | C | ✅ confidence control on a held-out group, distribution monitor, claim veto from confident input rows |
| README: how it works, start guide, predicted score | C | ⏸ not now |
| Video on the 20 sample rows | all | ⏳ 29 Oct, 09:00 |
| Pull request to QA-DNA | C | ⏳ 29 Oct, before 11:00 |

## Numbers (practice data, every fifth label hidden, as `check.sh` does)

| Metric | Value |
|---|---|
| Hidden rows labelled right | **340 / 380** (89.5%); 331 before this merge, 329 this morning; always `true` would score 85% |
| False sentences caught | **27 of 49** (22 before, 9 this morning); true rows called false: 11 (15 before) |
| Answers at confidence 0.9+ | 196, 96% right |
| Label calibration (A, out of fold) | accuracy 86.6%; ECE 0.027; no bin more than 0.05 below its confidence |
| Weakest band | `false` at 0.5–0.8: about 57% right; `true` at 0.5–0.6: 65% right |
| `unsure` predicted | never (A's default; a team decision once scoring is known) |
| Claims | 1,000: 383 at_event, 317 change, 294 compare (dates), 4 fact (dates), 2 relation |
| Claim confidence | measured on unseen rows: 294 at 0.971, 700 at 0.95 (capped), 4 at 0.867, 2 at 0.80; mean 0.956 |
| Full run time | ~11 s on practice with the controls; 131 s on our **synthetic** 20,000-row input (of 30 min) |
| Tests | 178 Python tests pass (`.venv/bin/pytest -q`); frontend type-checks, lints and builds; all 4 pages and 5 API routes checked live |

### Claim backtest (`scripts/backtest_claims.py` → `reports/claims_calibration.json`)

Claims built from the practice rows before 1 May, 1 Jul and 1 Sep, then judged twice:
- **full judge**: all practice rows. Partly circular, because the rows a claim came from also judge it.
- **strict judge**: only the rows dated after the cut-off, which the generator never saw.

Confidence is the lower of the two Wilson lower bounds (95%). If the strict judge can't check a group, its confidence is capped at 0.95.

| Group | Full judge | Strict judge | Decision | Confidence |
|---|---|---|---|---|
| compare (dates) | 1,211/1,211 | 127/127 | kept | 0.971 |
| at_event | 522/522 | can't check | kept, capped | 0.95 |
| change | 350/350 | can't check | kept, capped | 0.95 |
| fact (dates) | 65/65 | 25/25 | kept | 0.867 |
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
| Claims | Input rows labelled `true` at ≥ 0.9 are added as evidence; a candidate they contradict is vetoed and replaced from the reserve | 192 rows, 0 vetoed | 10,682 rows, 150 vetoed, 1,000 claims still filled |

**The 20,000-row input is synthetic, made by us:** the 1,897 practice rows plus 18,103 copies of practice sentences with new ids, dates shifted by up to ±60 days and empty labels. We do not have the organisers' 18,000 rows. It tests speed, limits and that the controls react to noise; it says nothing about our accuracy on new text, and its 150 vetoes and factor 0.6 react to our artificial noise, not to the real data.

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

## Next, by owner

**C (platform)**
1. Parked: README (how it works, start guide, predicted score).
2. Clean-up before the PR: `test.csv` (now 104 rows) to a demo folder; drop `.claude/launch.json`.

**A (engine)**
1. The weak bands: `false` at 0.5–0.8 (~57% right), `true` at 0.5–0.6 (65% right).
2. More false sentences (27 / 49).
3. Batch corroboration: check a row never confirms itself and copies are not counted as independent sources.

**B (frontend)**
1. Rehearse the demo script; record the video from `npm run build && npm start` (no dev indicator).
2. Technique names on every diagram box (`PLAN_NEXT.md` §3, Architecture).

**Team**
- Ask the organisers how confidence and `unsure` are scored. It sets `ARENA_UNSURE_BELOW`.

## Known risks

- Practice is ~10% of the final input: new facts and later value changes we cannot see.
- Claims now avoid values that can go stale (the backtest showed 52–71% right for them) and dates that move (`latest_*`, `next_*`, `planned_*`, `*_since`); the 1,000 are one-time dates, changes and event values.
- at_event and change claims can't be checked on unseen rows, so their 0.95 is a cap, not a measurement.
- Up to 30 claims rest on one fact; if a fact in our data is wrong, its claims fail together.
- The local `check.sh` label count (340/380) is an upper bound: the image's model was trained on all practice rows. The honest figure is 86.6% out of fold, against 83% for always `true`.

## Log

| When | What |
|---|---|
| 28 Oct, evening | C: run-time controls, as the organisers asked. A held-out control group recalibrates confidence on the real input (it can only lower it), a distribution monitor, and a claim veto from the input rows the engine is sure of. `check.sh` passes; our synthetic 20,000-row input in 131 s; 178 tests pass. |
| 28 Oct, evening | C: `Dockerfile` (python 3.12 slim, `jsonschema` only, `USER 10001`). `scripts/check.sh` passes in Docker. A synthetic 20,000-row input made by us (practice sentences copied with shifted dates; 18,103 unlabelled) under the judges' limits (offline, read-only, 2 CPUs, 6 GiB) runs in 63 s; output 0.67 MB. |
| 28 Oct, evening | C: claim confidence made honest. Moving dates (`latest_release_date` etc.) dropped after a strict check found a stale claim. The backtest now has a strict judge (unseen rows only); confidence is the lower bound of both judges and capped at 0.95 where the strict judge can't check. 993 claims at 0.99 became 294 at 0.971 and 700 at 0.95. 169 tests pass. |
| 28 Oct, 16:30 | Merged `dev/a` (engine: boosted trees, self-training, label calibration), `dev/b` (confidence page, Next.js 15.5.28, demo script), `dev/c`; no conflicts. 340/380 right, false caught 27/49; 167 tests pass; claim backtest unchanged; C fixed `/metrics` to the agreed shape (`n`, shipped groups only). After pulling, run `npm ci` in `frontend/`. |
| 28 Oct, 15:55 | `dev/c` (local): claim backtest and measured confidence (993 claims at 0.99; stale `fact` groups dropped); runner and API use A's `label_rows` (331/380 right, false caught 9 → 22); `GET /metrics`. |
| 28 Oct, 15:10 | Claim generator + validator: 1,000 valid claims; runner passes the official format checker. API: `/claims` and evidence texts. Frontend: Claims page, claim steps in the replay, evidence sentences in the detail panel. |
| 28 Oct, ~13:15 | Engine merged into `integration`; first live run with the real engine (4-row demo). |
| 28 Oct, ~12:00 | API and frontend merged into `integration`; contract checked field by field. |
