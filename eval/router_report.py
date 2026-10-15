"""Router accuracy on 20 hand-labelled queries (eval/router_queries.jsonl), separate from the unit tests.

    cd backend && SUPABASE_DB_URL=... python ../eval/router_report.py

Each query is labelled with the *ideal* route (companies, periods, intent), including cases the current rules
are known not to handle (sector questions, "best", "this quarter"), so the score isn't flattering.
"last quarter"-style periods are resolved against the latest ingested quarter per company in the database.
"""
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg

import check_manifest as cm
from generate.answer import latest_periods
from generate.router import route


def main():
    companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
    items = [json.loads(line) for line in (ROOT / "eval/router_queries.jsonl").read_text().splitlines() if line]
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        latest = latest_periods(conn)
    rows, score = [], {"companies": 0, "periods": 0, "intent": 0, "all_three": 0}
    for it in items:
        rt = route(it["question"], companies, latest, enabled=True)
        ok = {"companies": sorted(rt.companies) == sorted(it["companies"]),
              "periods": sorted(rt.periods) == sorted(it["periods"]),
              "intent": rt.kind == it["kind"]}
        ok["all_three"] = all(ok.values())
        for k, v in ok.items():
            score[k] += v
        rows.append({"id": it["id"], "question": it["question"], "expected": {k: it[k] for k in ("kind", "companies", "periods")},
                     "got": {"kind": rt.kind, "companies": rt.companies, "periods": rt.periods, "reason": rt.reason}, "ok": ok})
        if not ok["all_three"]:
            bad = [k for k in ("companies", "periods", "intent") if not ok[k]]
            print(f"MISS {it['id']} {bad}: {it['question']}\n     expected {it['kind']} {it['companies']} {it['periods']}"
                  f"\n     got      {rt.kind} {rt.companies} {rt.periods}  ({rt.reason})")
    n = len(items)
    summary = {k: f"{v}/{n} ({v / n:.0%})" for k, v in score.items()}
    print(summary, "latest ingested:", latest)
    (ROOT / "eval/results/router_report.json").write_text(json.dumps(
        {"latest_ingested": latest, "summary": summary, "queries": rows}, indent=2))


if __name__ == "__main__":
    main()
