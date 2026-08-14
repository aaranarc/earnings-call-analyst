from fastapi import FastAPI
from pydantic import BaseModel
from app.services.rag_service import RAGService

app = FastAPI()

# loaded once when the server starts, not per-request
service = RAGService()

class AskRequest(BaseModel):
    question: str

@app.post("/ask")
def ask(request: AskRequest):
    return service.ask(request.question)

@app.get("/companies")
def get_companies():
    all_data = service.collection.get()
    combos = set()
    all_metadatas = all_data.get("metadatas") or []
    for meta in all_metadatas:
        combos.add((meta["company"], meta["market"], meta["quarter"], meta["year"]))
    return [
        {"company": c, "market": m, "quarter": q, "year": y}
        for c, m, q, y in combos
    ]

from typing import Optional

class RiskRequest(BaseModel):
    financial_ratios: Optional[dict] = None
    company_name: Optional[str] = None

@app.post("/risk-score")
def risk_score(request: RiskRequest):
    return service.predict_risk(
        financial_ratios=request.financial_ratios, 
        company_name=request.company_name
    )