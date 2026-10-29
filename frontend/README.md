# Frontend: Hype Arena dashboard

**Start everything** from the repository root (Python 3.12, Node 20+): `scripts/start.sh`.
It starts the engine API on port 8000 and this app on **http://localhost:8080**. Ctrl+C stops both.
Frontend only, with the API already running: `npm ci && npm run dev`.

Pages:
- **Overview** (`/`): the system and the practice universe over time.
- **Live run** (`/run`): upload a CSV with `id,text,date,label`; rows with an empty label are checked by the real engine, labelled rows are context. Each verdict shows its evidence. Download the result as CSV (the six `output.csv` columns) or for Excel. Try `../data/test/demo.csv` (answers in `demo_key.csv`).
- **Claims** (`/claims`): the 1,000 claims the batch run writes, with their evidence.
- **Confidence** (`/confidence`): "we said X, we were right Y" for labels and claim types, the shift test and the run-time controls, from `GET /metrics`. Measured on rows the models never learned from (`eval/calibration_labels.json`, `reports/claims_calibration.json`, `reports/shift_test.json`, `reports/controls.json`).
- **Architecture** (`/architecture`) and **Dataset** (`/dataset`).

The browser calls `/api` on this server, which forwards to the API (`ARENA_API_URL`, default `http://127.0.0.1:8000`). If the API is down, the pages say so; a page that shows fixture data marks it as simulated.
