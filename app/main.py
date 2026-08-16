from typing import Optional

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()

_service = None

def get_service():
    global _service
    if _service is None:
        from app.services.rag_service import RAGService
        _service = RAGService()
    return _service

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask(request: AskRequest):
    try:
        svc = get_service()
        result = svc.ask(request.question)
        return result
    except Exception as e:
        import traceback
        return JSONResponse(
            status_code=500,
            content={"error": str(e), "traceback": traceback.format_exc()}
        )

@app.get("/companies")
def get_companies():
    try:
        svc = get_service()
        all_data = svc.collection.get()
        combos = set()
        all_metadatas = all_data.get("metadatas") or []
        for meta in all_metadatas:
            market = meta.get("market", meta.get("country", "Unknown"))
            combos.add((meta.get("company", "Unknown"), market, meta.get("quarter", "Unknown"), meta.get("year", "Unknown")))
        return [
            {"company": c, "market": m, "quarter": q, "year": y}
            for c, m, q, y in combos
        ]
    except Exception as e:
        import traceback
        return {"error": str(e), "traceback": traceback.format_exc()}

class RiskRequest(BaseModel):
    financial_ratios: Optional[dict] = None
    company_name: Optional[str] = None

@app.post("/risk-score")
def risk_score(request: RiskRequest):
    try:
        return get_service().predict_risk(
            financial_ratios=request.financial_ratios, 
            company_name=request.company_name
        )
    except Exception as e:
        import traceback
        return JSONResponse(status_code=500, content={"error": str(e), "traceback": traceback.format_exc()})
@app.get("/health/memory")
def health_memory():
    import os
    import psutil
    process = psutil.Process(os.getpid())
    mem_info = process.memory_info()
    return {
        "rss_mb": mem_info.rss / 1024 / 1024,
        "vms_mb": mem_info.vms / 1024 / 1024,
        "status": "ok"
    }
