"""HTTP adapter for the frontend: validates the request, calls the engine, serializes the answer.

The engine is built once, at startup, from the practice data in the repository.
Demo mode (ARENA_DEMO=1) uses the synthetic engine of tests/fixtures_c and says so in
every answer. It is never a fallback: without it, a missing engine is a 503.

    uvicorn api.main:app --port 8000
"""
import os
import re
import threading
import traceback
from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator

from arena.generate import select_claims
from arena.io import InputError, parse_rows, read_lexicon, read_rows
from arena.runner import AS_OF, CLAIMS, HERE, Pipeline

MAX_ROWS = 5000
MAX_UPLOAD_BYTES = 5 * 1024 * 1024
DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class Row(BaseModel):
    id: str = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=5000)
    date: str
    label: Literal["", "true", "false", "unsure"] = ""

    @field_validator("id", "text", "date", mode="before")
    @classmethod
    def strip(cls, v):
        return v.strip() if isinstance(v, str) else v

    @field_validator("date")
    @classmethod
    def iso_date(cls, v):
        if not DATE.match(v):
            raise ValueError("date must be YYYY-MM-DD")
        return v


class PredictRequest(BaseModel):
    rows: list[Row] = Field(min_length=1, max_length=MAX_ROWS)


class State:
    pipeline = None
    demo = False
    error = None
    sources = {}        # practice row id -> {id, text, date, label}, to show evidence
    claims = None       # the claims the batch run writes, built once at startup
    claims_error = None


def _load(state, engine, demo):
    data = os.environ.get("ARENA_DATA", os.path.join(HERE, "data"))
    practice = read_rows(os.path.join(data, "practice.csv"), require_form=True)
    lexicon = read_lexicon(os.path.join(data, "lexicon.json"))
    if demo and engine is None:
        from tests.fixtures_c.fake_engine import ENGINE
        engine = ENGINE
    state.demo = demo
    state.sources = {r["id"]: {k: r[k] for k in ("id", "text", "date", "label")} for r in practice}
    try:
        claims, report = select_claims(practice, lexicon, AS_OF, [r["text"] for r in practice], CLAIMS)
        state.claims = {"claims": [_public_claim(c, state.sources) for c in claims],
                        "report": report, "as_of": AS_OF}
    except Exception as e:
        traceback.print_exc()
        state.claims_error = f"claim generator failed: {type(e).__name__}: {e}"
    try:
        state.pipeline = Pipeline(practice, lexicon, engine)
    except Exception as e:
        traceback.print_exc()
        state.error = f"engine unavailable: {type(e).__name__}: {e}"


def _evidence(ids, sources):
    """The practice rows behind a verdict or a claim, for display."""
    return [sources[i] for i in ids if i in sources]


def _public_claim(c, sources):
    return {"id": c["id"], "type": c["type"], "text": c["text"], "form": c["form"],
            "confidence": c["confidence"], "evidence_ids": c["evidence_ids"],
            "evidence": _evidence(c["evidence_ids"], sources)}


def create_app(engine=None, demo=None):
    """engine: contract v1 functions to use instead of A's modules (tests)."""
    if demo is None:
        demo = os.environ.get("ARENA_DEMO") == "1"
    state = State()

    @asynccontextmanager
    async def lifespan(app):
        _load(state, engine, demo)
        yield

    app = FastAPI(title="Git Happens — Temporal Truth Engine API", lifespan=lifespan)
    app.state.engine = state

    def pipeline():
        if state.pipeline is None:
            raise HTTPException(503, state.error or "engine not loaded")
        return state.pipeline

    engine_lock = threading.Lock()  # the batch updates the engine's shared state

    def predict_rows(rows):
        """As the batch runner labels: the whole upload at once (page context), else row by row."""
        p = pipeline()
        with engine_lock:
            try:
                batch = p.label_all(rows)
            except Exception:
                traceback.print_exc()
                batch = None
            if batch is not None:
                for pred in batch:
                    pred["evidence"] = _evidence(pred.get("evidence_ids") or [], state.sources)
                return batch
            return [one(p, row) for row in rows if not row["label"]]

    def one(p, row):
        try:
            pred = p.predict(row)
            pred["evidence"] = _evidence(pred.get("evidence_ids") or [], state.sources)
            return pred
        except Exception as e:
            traceback.print_exc()
            return {"id": row["id"], "label": "unsure", "confidence": None, "evidence_ids": [],
                    "reason": "The engine failed on this row.", "error": f"{type(e).__name__}: {e}",
                    "evidence": [], "extraction": {"facts": [], "complete": False, "issues": ["engine error"]}}

    def check_unique(rows):
        seen = set()
        for r in rows:
            if r["id"] in seen:
                raise HTTPException(422, f"duplicate id {r['id']!r}")
            seen.add(r["id"])

    @app.get("/health")
    def health():
        if state.pipeline is None:
            raise HTTPException(503, state.error or "engine not loaded")
        return {"status": "ok", "demo_mode": state.demo}

    @app.get("/claims")
    def claims():
        """The claims the batch run writes for this practice data, with their evidence."""
        if state.claims is None:
            raise HTTPException(503, state.claims_error or "claims not built")
        return {**state.claims, "demo_mode": state.demo}

    @app.post("/predict")
    def predict(request: PredictRequest):
        rows = [r.model_dump() for r in request.rows]
        check_unique(rows)
        return {"predictions": predict_rows(rows), "demo_mode": state.demo}

    @app.post("/predict/csv")
    def predict_csv(file: UploadFile = File(...)):
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(413, f"file over {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
        try:
            rows = parse_rows(data)
        except InputError as e:
            raise HTTPException(422, f"invalid CSV: {e}")
        if len(rows) > MAX_ROWS:
            raise HTTPException(413, f"more than {MAX_ROWS} rows")
        for n, r in enumerate(rows, start=2):
            if not r["text"] or not DATE.match(r["date"]):
                raise HTTPException(422, f"invalid CSV: line {n}: empty text or date not YYYY-MM-DD")
        rows = [{k: r[k] for k in ("id", "text", "date", "label")} for r in rows]
        return {"rows": rows, "predictions": predict_rows(rows), "demo_mode": state.demo}

    return app


app = create_app()
