"""Local dashboard API. Start from the repository root; see frontend/README.md."""
import asyncio
import csv
import json
import os
import secrets
import sys
from contextlib import asynccontextmanager
from dataclasses import asdict
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from starlette.concurrency import run_in_threadpool

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
@asynccontextmanager
async def lifespan(app):
    if os.getenv("APP_ENV") == "production" and len(os.getenv("API_ACCESS_TOKEN", "")) < 32:
        raise RuntimeError("Production requires a server-only API_ACCESS_TOKEN of at least 32 characters")
    yield


app = FastAPI(title="QuantRAG", version="2.0.0-alpha", lifespan=lifespan)


@app.middleware("http")
async def access_control(request: Request, call_next):
    from starlette.responses import JSONResponse
    if request.method == "POST":
        token = os.getenv("API_ACCESS_TOKEN", "")
        if (os.getenv("APP_ENV") == "production" and len(token) < 32) or (
                token and not secrets.compare_digest(request.headers.get("authorization", "").encode(), ("Bearer " + token).encode())):
            return JSONResponse({"detail": "API access denied"}, status_code=401)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response

lock = asyncio.Lock()
_models = None


class Question(BaseModel):
    question: str = Field(min_length=3, max_length=2000)

    @field_validator("question")
    @classmethod
    def nonempty(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Enter a question of at least three characters")
        return value.strip()


@app.get("/health")
def health():
    return {"status": "ok", "configured": all(os.getenv(k) for k in ("SUPABASE_DB_URL", "GEMINI_API_KEY", "GEMINI_MODEL")),
            "models_loaded": _models is not None}


@app.get("/companies")
def companies():
    import yaml
    entries = yaml.safe_load((ROOT / "data/companies.yaml").read_text())
    stats = json.loads((ROOT / "eval/results/ingest_stats.json").read_text())
    with (ROOT / "data/manifest.csv").open() as f:
        manifest = {(r["symbol"], r["fiscal_label"]): r for r in csv.DictReader(f)}
    for company in entries:
        company["documents"] = [dict(d, source_url=manifest.get((d["symbol"], d["fiscal_label"]), {})
                                     .get("source_url")) for d in stats["documents"] if d["symbol"] == company["symbol"]]
    return {"companies": entries, "as_of": stats["date"], "source": "committed ingest snapshot"}


@app.get("/eval/latest")
def evaluation():
    # No inferred scores or automatic promotion of development smoke results to gold metrics.
    path = ROOT / "eval/results/public_eval.json"
    if not path.exists():
        return {"status": "pending", "metrics": [], "ablations": [], "failure_cases": [],
                "agreement": None, "last_run": None}
    return json.loads(path.read_text())


def source_neighbors(conn, chunk_id):
    """Adjacent stored chunks from the same document, not inferred conversational turns."""
    rows = conn.execute("""
        with target as (select document_id, id from chunks where id = %(id)s),
        before_chunk as (
            select c.id, c.speaker, c.role, c.section, c.page, c.text
            from chunks c, target t where c.document_id = t.document_id and c.id < t.id
            order by c.id desc limit 1
        ), after_chunk as (
            select c.id, c.speaker, c.role, c.section, c.page, c.text
            from chunks c, target t where c.document_id = t.document_id and c.id > t.id
            order by c.id limit 1
        )
        select 'before', * from before_chunk union all select 'after', * from after_chunk
    """, {"id": chunk_id}).fetchall()
    return [dict(zip(("position", "chunk_id", "speaker", "role", "section", "page", "text"), row)) for row in rows]


def run_answer(question):
    import psycopg
    from pgvector.psycopg import register_vector

    from generate.answer import answer
    from retrieve.search import Models

    global _models
    if _models is None:
        _models = Models(rerank=True)
    entries = companies()["companies"]
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=10,
                         options="-c search_path=quantrag,public,extensions -c statement_timeout=30000") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        register_vector(conn)
        result = answer(question, conn, _models, {c["symbol"]: c for c in entries})
        cited_ids = {c["chunk_id"] for c in result["citations"]}
        neighbors = {h.chunk_id: source_neighbors(conn, h.chunk_id) for h in result["hits"] if h.chunk_id in cited_ids}
    sources = {(c["symbol"], d["fiscal_label"]): d.get("source_url")
               for c in entries for d in c["documents"]}
    result["hits"] = [dict(asdict(h), source_url=sources.get((h.symbol, h.fiscal_label)), context=neighbors.get(h.chunk_id, [])) for h in result["hits"]]
    return result


@app.post("/ask")
async def ask(body: Question):
    if not all(os.getenv(k) for k in ("SUPABASE_DB_URL", "GEMINI_API_KEY", "GEMINI_MODEL")):
        raise HTTPException(503, "Analyst is not configured. Start the API with the project environment.")
    if lock.locked():
        raise HTTPException(429, "The analyst is handling another question. Try again shortly.",
                            headers={"Retry-After": "10"})
    reserve_budget()
    await lock.acquire()

    async def stream():
        try:
            message = "Warming up the analyst…" if _models is None else "Retrieving cited evidence…"
            yield f"event: status\ndata: {json.dumps(message)}\n\n"
            result = await run_in_threadpool(run_answer, body.question)
            yield f"event: answer\ndata: {json.dumps(result)}\n\n"
        except Exception:  # noqa: BLE001 -- API boundary must redact provider/driver error details
            # Driver/provider exceptions can include connection details. Keep them out of responses.
            yield 'event: error\ndata: "The analyst could not finish. Check the connection and try again."\n\n'
        finally:
            lock.release()
    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def reserve_budget(units=1):
    from quantrag.usage import BudgetExceeded, reserve
    try:
        reserve(units)
    except BudgetExceeded as exc:
        raise HTTPException(429, "Today's analyst budget is used up. Please return tomorrow.",
                            headers={"Retry-After": "3600"}) from exc


class ThesisQuestion(BaseModel):
    symbol: str = Field(min_length=1, max_length=30, pattern=r"^[A-Z]+$")
    thesis: str = Field(min_length=3, max_length=2000)
    periods: list[str] = Field(min_length=1, max_length=4)

    @field_validator("periods")
    @classmethod
    def period_labels(cls, values):
        import re
        if len(set(values)) != len(values) or any(not re.fullmatch(r"Q[1-4] FY\d{2}", v) for v in values):
            raise ValueError("Choose distinct fiscal periods, e.g. Q1 FY27")
        return values

    @field_validator("thesis")
    @classmethod
    def nonempty(cls, value):
        if len(value.strip()) < 3:
            raise ValueError("Enter a thesis of at least three characters")
        return value.strip()


def run_thesis(body):
    import psycopg
    from pgvector.psycopg import register_vector

    from generate.thesis import check_thesis
    from retrieve.search import Models

    global _models
    if _models is None:
        _models = Models(rerank=True)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], connect_timeout=10,
                         options="-c search_path=quantrag,public,extensions -c statement_timeout=30000") as conn:
        conn.execute("SET TRANSACTION READ ONLY")
        register_vector(conn)
        result = check_thesis(body.thesis, body.symbol, body.periods, conn, _models)
    sources = {(c["symbol"], d["fiscal_label"]): d.get("source_url")
               for c in companies()["companies"] for d in c["documents"]}
    for suggestion in result["suggestions"]:
        for e in suggestion["evidence"]:
            e["source_url"] = sources.get((e["symbol"], e["period"]))
    return result


@app.post("/thesis/check")
async def thesis_check(body: ThesisQuestion):
    if not all(os.getenv(k) for k in ("SUPABASE_DB_URL", "GEMINI_API_KEY", "GEMINI_MODEL")):
        raise HTTPException(503, "Analyst is not configured.")
    entries = {c["symbol"]: c for c in companies()["companies"]}
    if body.symbol not in entries or any(p not in [d["fiscal_label"] for d in entries[body.symbol]["documents"]]
                                         for p in body.periods):
        raise HTTPException(422, "Choose an ingested company and its available periods.")
    if lock.locked():
        raise HTTPException(429, "The analyst is handling another question.", headers={"Retry-After": "10"})
    reserve_budget(len(body.periods))
    async with lock:
        try:
            return await run_in_threadpool(run_thesis, body)
        except ValueError as exc:
            raise HTTPException(422, "Requested transcript coverage is unavailable.") from exc
        except Exception as exc:
            raise HTTPException(502, "The analyst could not finish the thesis check. Please retry.") from exc
