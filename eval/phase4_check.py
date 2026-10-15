"""Phase 4 done-check: 10 answerable questions get valid citations, 3 unanswerable ones are refused.

    cd backend && SUPABASE_DB_URL=... GEMINI_API_KEY=... GEMINI_MODEL=... python ../eval/phase4_check.py

"Valid" = not refused, at least one citation, every citation points at a provided chunk (enforced by
generate.answer.validate), every cited chunk belongs to a company the question is about, and at least one cited
chunk contains an expected quote (per company, for comparisons). Full answers go to eval/results/phase4_check.json
for human review: these checks don't judge faithfulness (Phase 6 does).
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg
from pgvector.psycopg import register_vector

import check_manifest as cm
from generate.answer import answer
from retrieve.search import Models

SMOKE = {json.loads(line)["id"]: json.loads(line) for line in (ROOT / "eval/smoke.jsonl").read_text().splitlines()}
ANSWERABLE = [
    {"q": SMOKE[i]["question"], "expect": {SMOKE[i]["symbol"]: SMOKE[i]["quotes"]}}
    for i in ("s01", "s03", "s04", "s06", "s07", "s09", "s13", "s19")
] + [
    {"q": "Compare TCS and Infosys on large deal wins", "expect": {"TCS": ["$9.5 billion"], "INFY": ["21 large deals"]}},
    {"q": "Compare HUL and HDFC Bank on how they described demand in the June 2026 quarter",
     "expect": {"HINDUNILVR": [""], "HDFCBANK": [""]}},  # any chunk of each company counts
]
UNANSWERABLE = [
    "What was Wipro's revenue growth in Q1 FY27?",                    # covered company, no transcript ingested
    "What did TCS say about its Q3 FY26 results?",                     # quarter not ingested
    "What is Hindustan Unilever's share price target for next year?",  # not something calls contain
]
OUT_OF_SCOPE = ["What's the weather in Mumbai tomorrow?"]


def main():
    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    models = Models(rerank=True)
    results = []
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        for kind, items in (("answerable", ANSWERABLE), ("unanswerable", [{"q": q} for q in UNANSWERABLE]),
                            ("out_of_scope", [{"q": q} for q in OUT_OF_SCOPE])):
            for it in items:
                out = answer(it["q"], conn, models, companies)
                texts = {h.chunk_id: h.text for h in out["hits"]}
                row = {"kind": kind, "question": it["q"], "route": out["route"], "refused": out["refused"],
                       "refusal_reason": out["refusal_reason"], "answer_markdown": out["answer_markdown"],
                       "comparison_table": out["comparison_table"], "citations": out["citations"],
                       "timing_s": {k: round(v, 2) for k, v in out["timing_s"].items()}}
                if kind == "answerable":
                    cited = out["citations"]
                    row["checks"] = {
                        "not_refused": not out["refused"],
                        "has_citations": bool(cited),
                        "cites_only_asked_companies": all(c["symbol"] in it["expect"] for c in cited),
                        "cites_expected_evidence": all(
                            any(c["symbol"] == sym and any(q in texts[c["chunk_id"]] for q in quotes) for c in cited)
                            for sym, quotes in it["expect"].items()),
                    }
                    row["pass"] = all(row["checks"].values())
                else:
                    row["pass"] = out["refused"]
                results.append(row)
                print(f"{'PASS' if row['pass'] else 'FAIL'} [{kind}] {it['q'][:70]}"
                      + ("" if kind != "answerable" else f"  {row['checks']}"))
    summary = {k: f"{sum(r['pass'] for r in results if r['kind'] == k)}/{sum(r['kind'] == k for r in results)}"
               for k in ("answerable", "unanswerable", "out_of_scope")}
    print(summary)
    (ROOT / "eval/results/phase4_check.json").write_text(json.dumps(
        {"gemini_model": os.environ.get("GEMINI_MODEL"), "summary": summary, "results": results}, indent=2,
        ensure_ascii=False))


if __name__ == "__main__":
    main()
