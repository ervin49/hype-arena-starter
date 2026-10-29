# API (FastAPI) — for the frontend

```sh
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
.venv/bin/uvicorn api.main:app --port 8000                  # real engine (A's modules)
ARENA_DEMO=1 .venv/bin/uvicorn api.main:app --port 8000     # synthetic engine, demo_mode: true
```

Without the real engine and without `ARENA_DEMO=1`, every endpoint answers 503 with the reason.

| Endpoint | Body | Answer |
| --- | --- | --- |
| `GET /health` | — | `{"status": "ok", "demo_mode": bool}`, or 503 |
| `POST /predict` | `{"rows": [{"id", "text", "date": "YYYY-MM-DD", "label": ""}]}` | `{"predictions": [...], "demo_mode": bool}` |
| `POST /predict/csv` | multipart, field `file`: CSV with `id,text,date,label` | `{"rows": [...], "predictions": [...], "demo_mode": bool}` |

Only unlabelled rows are classified; labelled rows stay in `rows`. Each prediction holds
`id`, `label`, `confidence` (null for unsure), `evidence_ids`, `reason` and `extraction`
(`facts`, `complete`, `issues`); a row the engine failed on also holds `error`.
Errors: 422 for a bad request or CSV (the reason in `detail`), 413 over 5 MB or 5,000 rows.
