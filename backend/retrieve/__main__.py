"""python -m retrieve "question" [--company TCS ...] [--period "Q1 FY27" ...] [--mode hybrid] [--no-rerank]

Prints the ranked chunks with their dense, FTS, RRF and rerank scores. Needs SUPABASE_DB_URL.
"""
import argparse
import os

import psycopg
from pgvector.psycopg import register_vector

from retrieve.search import Models, retrieve


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--company", action="append")
    ap.add_argument("--period", action="append")
    ap.add_argument("--mode", choices=["dense", "fts", "hybrid"], default="hybrid")
    ap.add_argument("--no-rerank", action="store_true")
    ap.add_argument("-n", type=int, default=5)
    a = ap.parse_args()
    models = Models(rerank=not a.no_rerank)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        hits = retrieve(conn, models, a.question, a.company, a.period, a.mode, not a.no_rerank, top_n=a.n)
    fmt = lambda h, s: f"{h.scores[s]:.3f}#{h.scores[s + '_rank']}" if s in h.scores else "-"
    print(f"{'#':>2} {'chunk':>6} {'doc':18} {'dense':>11} {'fts':>11} {'rrf':>11} {'rerank':>11}  speaker")
    for i, h in enumerate(hits, 1):
        print(f"{i:2} {h.chunk_id:6} {h.symbol + ' ' + h.fiscal_label:18} {fmt(h, 'dense'):>11} {fmt(h, 'fts'):>11} "
              f"{fmt(h, 'rrf'):>11} {fmt(h, 'rerank'):>11}  {h.speaker} ({h.role}, p{h.page})")
        print(f"   {h.text[:150]!r}")


if __name__ == "__main__":
    main()
