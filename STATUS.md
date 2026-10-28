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
| Claim generator + validator: 1,000 claims | C | ✅ 1,000 valid; confidence measured by backtest; pool ~1,300 |
| Confidence chart (`/metrics` → `/confidence` page) | B | ✅ real measured numbers, labels and claims |
| Label calibration (`eval/calibration_labels.json`) | A | ✅ Platt, cross-fitted; ECE 0.027 |
| Demo script (`frontend/docs/demo-script.md`) | B | ✅ draft |
| `Dockerfile` + `scripts/check.sh` in Docker | C | ⏸ parked for now — **required for the judges to run anything** |
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
| Claims | 1,000: 383 at_event, 316 change, 294 compare (dates), 5 fact (dates), 2 relation |
| Claim confidence | measured: 993 at 0.99, 5 at 0.95, 2 at 0.80 (relation, not measurable) |
| Full run time | ~2.6 s and 54 MB on practice; the ~20,000-row run is estimated at about 1 min of 30 |
| Tests | 167 Python tests pass (`.venv/bin/pytest -q`); frontend type-checks, lints and builds; all 4 pages and 5 API routes checked live |

### Claim backtest (`scripts/backtest_claims.py` → `reports/claims_calibration.json`)

Claims built from the practice rows before 1 May, 1 Jul and 1 Sep, judged on the rows after.

| Group | Judged | Right | Decision | Confidence |
|---|---|---|---|---|
| compare (dates) | 1,229 | 100% | kept | 0.99 |
| at_event | 522 | 100% | kept | 0.99 |
| change | 350 | 100% | kept | 0.99 |
| fact (dates) | 67 | 100% | kept | 0.95 |
| fact (values that never changed) | 113 | 52% | dropped | — |
| fact (values that changed before) | 51 | 71% | dropped | — |
| compare (amounts) | 29 | 97% | dropped (bar: 98% at every cut-off) | — |
| relation | — | not judged | kept, cautious | 0.80 |

Caveat: dates and events are judged partly on the same practice data plus the later reports; strong evidence, not proof. The final input is ~10× larger.

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
1. Parked: `Dockerfile` + `scripts/check.sh` (needed for the judges to run anything); README (how it works, start guide, predicted score).
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
- Claims now avoid values that can go stale (the backtest showed 52–71% right for them); the 1,000 are dates, changes and event values.
- Up to 30 claims rest on one fact; if a fact in our data is wrong, its claims fail together.
- Without the Dockerfile there is no submission. It is parked, not dropped.

## Log

| When | What |
|---|---|
| 28 Oct, 16:30 | Merged `dev/a` (engine: boosted trees, self-training, label calibration), `dev/b` (confidence page, Next.js 15.5.28, demo script), `dev/c`; no conflicts. 340/380 right, false caught 27/49; 167 tests pass; claim backtest unchanged; C fixed `/metrics` to the agreed shape (`n`, shipped groups only). After pulling, run `npm ci` in `frontend/`. |
| 28 Oct, 15:55 | `dev/c` (local): claim backtest and measured confidence (993 claims at 0.99; stale `fact` groups dropped); runner and API use A's `label_rows` (331/380 right, false caught 9 → 22); `GET /metrics`. |
| 28 Oct, 15:10 | Claim generator + validator: 1,000 valid claims; runner passes the official format checker. API: `/claims` and evidence texts. Frontend: Claims page, claim steps in the replay, evidence sentences in the detail panel. |
| 28 Oct, ~13:15 | Engine merged into `integration`; first live run with the real engine (4-row demo). |
| 28 Oct, ~12:00 | API and frontend merged into `integration`; contract checked field by field. |
