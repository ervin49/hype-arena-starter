# Git Happens — status

**Last updated:** 2026-10-28 15:10 EET, by C, on `integration`
**Deadline:** PR to QA-DNA open before **11:00 on 29 Oct**. Feature freeze at 08:00, sample at 09:00, video after.

> Updated on every merge into `integration`. If something here is out of date, tell C.

## At a glance

| Part | Owner | State |
|---|---|---|
| Engine: extraction, temporal check, ML verdict | A | ✅ works; false sentences are the weak spot |
| Frontend: upload, verdicts, claims, architecture replay | B (+ C for claims and evidence) | ✅ works with the real engine |
| API: `/health`, `/predict`, `/predict/csv`, `/claims` | C | ✅ works |
| Batch runner → `/output/output.csv` | C | ✅ passes the official format checker locally |
| Claim generator + validator: 1,000 claims | C | ✅ 1,000 valid, from a pool of ~1,280 |
| `Dockerfile` + `scripts/check.sh` in Docker | C | ❌ **not started — required to be run at all** |
| Start guide in the README | C | ❌ to do |
| Video on the 20 sample rows | all | ⏳ 29 Oct, 09:00 |
| Pull request to QA-DNA | C | ⏳ 29 Oct, before 11:00 |

## Numbers (practice data, every fifth label hidden, as `check.sh` does)

| Metric | Value |
|---|---|
| Hidden rows labelled right | 329 / 380 (86.6%); always `true` would score 85% |
| False sentences caught | 9 of 49: the main thing to improve |
| `unsure` predicted | never (A's default; a team decision once scoring is known) |
| Confidence 0.9+ is right | 95.5% of the time (A's cross-validation) |
| Claims | 1,000: 309 change, 247 at_event, 241 fact, 197 compare, 6 relation |
| Claim confidence | 0.83–0.97, most around 0.9 |
| Full run time | ~2 s on practice; the ~20,000-row run is estimated at about 1 min of 30 |
| Tests | 156 Python tests pass (`.venv/bin/pytest -q`); frontend builds and lints clean |

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
1. `Dockerfile`, then `scripts/check.sh` offline as user 10001. This is the most urgent item.
2. Runner: switch to A's `label_rows` (page context and corroboration).
3. Start guide in `README.md`; move `test.csv` to `demo/`; drop `.claude/launch.json` from the submission.

**A (engine)**
1. Catch more false sentences (9 / 49).
2. Calibrate confidence (0.9+ is right 95.5% of the time, so it can honestly be higher).
3. Note: `arena.values` reads `€59 per month or €590 per year` as a range; `value-forms.md` reads it as a choice.

**B (frontend)**
1. Update Next.js to a patched 15.5.x (15.5.4 has a published vulnerability).
2. Hide the dev indicator for the video, or record from `npm start`.
3. Review C's additions: the Claims page, claim steps in the replay, evidence text in the detail panel.

**Team**
- Ask the organisers how confidence and `unsure` are scored. It decides how cautious the engine should be.

## Known risks

- Practice is ~10% of the final input: new facts and later value changes we cannot see.
- `fact` and amount `compare` claims depend on values still holding on 29 Oct; dates, changes and event values cannot go stale.
- Without the Dockerfile there is no submission. It comes first.

## Log

| When | What |
|---|---|
| 28 Oct, 15:10 | Claim generator + validator: 1,000 valid claims; runner passes the official format checker. API: `/claims` and evidence texts. Frontend: Claims page, claim steps in the replay, evidence sentences in the detail panel. |
| 28 Oct, ~13:15 | Engine merged into `integration`; first live run with the real engine (4-row demo). |
| 28 Oct, ~12:00 | API and frontend merged into `integration`; contract checked field by field. |
