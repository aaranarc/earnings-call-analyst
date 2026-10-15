"""python -m generate "question" [--no-rerank]     needs SUPABASE_DB_URL, GEMINI_API_KEY, GEMINI_MODEL"""
import argparse
import os

import psycopg
from pgvector.psycopg import register_vector

import check_manifest as cm
from generate.answer import answer
from retrieve.search import Models


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--no-rerank", action="store_true")
    a = ap.parse_args()
    companies, _ = cm.load_companies(cm.ROOT / "data/companies.yaml")
    models = Models(rerank=not a.no_rerank)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        out = answer(a.question, conn, models, companies, use_rerank=not a.no_rerank)
    r = out["route"]
    print(f"route: {r['kind']} · companies {r['companies'] or 'all'} · periods {r['periods'] or 'all'} · "
          f"numeric {r['numeric']} ({r['reason']})")
    if out["refused"]:
        print(f"\nREFUSED: {out['refusal_reason']}")
    else:
        print(f"\n{out['answer_markdown']}\n")
        for row in out["comparison_table"] or []:
            print(f"  {row['metric']}: " + " | ".join(f"{c['company']}: {c['value']} {c['citations']}"
                                                     for c in row["cells"]))
        for c in out["citations"]:
            print(f"  [c{c['n']}] {c['symbol']} {c['fiscal_label']} · {c['speaker']} ({c['role']}) p{c['page']}")
    print("\ntiming (s): " + ", ".join(f"{k} {v:.2f}" for k, v in out["timing_s"].items()))


if __name__ == "__main__":
    main()
