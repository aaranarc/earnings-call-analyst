"""Corpus and database statistics, read-only, written to eval/results/ingest_stats.json.

    cd backend && SUPABASE_DB_URL=... python ../eval/ingest_stats.py

Token counts use the embedding model's own tokenizer on the stored chunk text.
"""
import datetime
import json
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))

import psycopg

from ingest.run import Embedder


def main():
    url = os.environ["SUPABASE_DB_URL"]
    tok = Embedder()
    with psycopg.connect(url, options="-c search_path=quantrag,public,extensions") as c:
        docs = c.execute("""select co.symbol, d.fiscal_label, count(ch.*), (select count(*) from chunk_numbers n
                            join chunks c2 on c2.id = n.chunk_id where c2.document_id = d.id)
                            from documents d join companies co on co.id = d.company_id
                            left join chunks ch on ch.document_id = d.id group by co.symbol, d.fiscal_label, d.id
                            order by co.symbol""").fetchall()
        texts = [t for (t,) in c.execute("select text from chunks")]
        schema_bytes, db_bytes = c.execute(
            """select (select sum(pg_total_relation_size(cl.oid)) from pg_class cl
                       join pg_namespace n on n.oid = cl.relnamespace where n.nspname = 'quantrag' and cl.relkind = 'r'),
                      pg_database_size(current_database())""").fetchone()
        host = c.info.host
    tokens = [tok.count(t) for t in texts]
    result = {
        "date": datetime.date.today().isoformat(),
        "database": "supabase" if "supabase" in (host or "") else "local",
        "documents": [{"symbol": s, "fiscal_label": f, "chunks": n, "numbers": k} for s, f, n, k in docs],
        "totals": {"documents": len(docs), "chunks": len(texts), "numbers": sum(d[3] for d in docs),
                   "avg_tokens_per_chunk": round(statistics.mean(tokens), 1),
                   "median_tokens_per_chunk": statistics.median(tokens), "max_tokens_per_chunk": max(tokens),
                   "quantrag_schema_mb": round(float(schema_bytes) / 2**20, 2), "database_mb": round(float(db_bytes) / 2**20, 1),
                   "supabase_free_tier_mb": 500},
        "manifest_target": {"companies": 12, "quarters": 8, "transcripts": 96},
    }
    out = ROOT / "eval/results/ingest_stats.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result["totals"]), "->", out.relative_to(ROOT))


if __name__ == "__main__":
    main()
