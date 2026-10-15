"""Ingest every complete manifest row into Postgres (schema quantrag).

    cd backend && python -m ingest.run            # needs SUPABASE_DB_URL
    cd backend && python -m ingest.run --dry-run  # parse + chunk + count every manifest PDF on disk; no DB, no embedding

Idempotent: a document whose sha256 is already in quantrag.documents is skipped. Each document is written in
one transaction, so a crash never leaves a half-ingested transcript behind.
Only rows that pass scripts/check_manifest.py are ingested; rows with errors or no file are reported and skipped.
"""
import os
import statistics
import sys
from pathlib import Path

import psycopg
from pgvector.psycopg import register_vector

from ingest.chunk import chunk_turns
from ingest.parse import parse_transcript
from numcheck.extract import extract

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
import check_manifest as cm

EMBED_MODEL = "BAAI/bge-small-en-v1.5"  # 384-d; must match vector(384) in db/schema.sql


class Embedder:
    """fastembed (ONNX) model + an untruncated copy of its tokenizer for counting chunk sizes."""

    def __init__(self):
        from fastembed import TextEmbedding
        from tokenizers import Tokenizer
        self.model = TextEmbedding(EMBED_MODEL)
        self.tok = Tokenizer.from_str(self.model.model.tokenizer.to_str())
        self.tok.no_truncation()
        self.tok.no_padding()

    def count(self, text):
        return len(self.tok.encode(text, add_special_tokens=False).ids)

    def embed(self, texts):
        return list(self.model.embed(texts, batch_size=32))


def embed_text(company, label, chunk):
    """What the vector represents: the chunk plus who said it, where. The stored text stays the raw chunk."""
    return f"{company} {label} · {chunk.speaker} ({chunk.role}): {chunk.text}"


def ingest(conn, manifest, companies_path, raw_dir, embedder_factory=Embedder, log=print):
    conn.execute((ROOT / "db/schema.sql").read_text())
    register_vector(conn)  # after the schema, which creates the vector extension on a fresh database
    companies, _ = cm.load_companies(companies_path)
    for c in companies.values():
        conn.execute("""insert into companies (symbol, name, sector, aliases) values (%s, %s, %s, %s)
                        on conflict (symbol) do update set name = excluded.name, sector = excluded.sector,
                        aliases = excluded.aliases""", (c["symbol"], c["name"], c["sector"], c["aliases"]))
    conn.commit()

    complete, _, errors, _ = cm.check(manifest, companies_path, raw_dir)
    for e in errors:
        log(f"skip (manifest error): {e}")
    rows = [r for r in cm.read_manifest(manifest) if (r["symbol"], r["fiscal_label"]) in complete]
    have = {s for (s,) in conn.execute("select sha256 from documents")}
    todo = [r for r in rows if r["sha256"] not in have]
    log(f"{len(rows)} complete rows · {len(rows) - len(todo)} already ingested · {len(todo)} to ingest")

    stats = {"documents": 0, "chunks": 0, "tokens": 0, "numbers": 0}
    embedder = embedder_factory() if todo else None
    for r in todo:
        chunks = chunk_turns(parse_transcript(Path(raw_dir) / r["filename"]), embedder.count)
        vectors = embedder.embed([embed_text(companies[r["symbol"]]["name"], r["fiscal_label"], c) for c in chunks])
        with conn.transaction():
            (doc_id,) = conn.execute(
                """insert into documents (company_id, fiscal_label, period_end, call_date, source_url, sha256)
                   select id, %s, %s, %s, %s, %s from companies where symbol = %s returning id""",
                (r["fiscal_label"], r["period_end"], r["call_date"], r["source_url"], r["sha256"], r["symbol"]),
            ).fetchone()
            for c, v in zip(chunks, vectors):
                (chunk_id,) = conn.execute(
                    """insert into chunks (document_id, speaker, role, section, page, text, embedding)
                       values (%s, %s, %s, %s, %s, %s, %s) returning id""",
                    (doc_id, c.speaker, c.role, c.section, c.page, c.text, v),
                ).fetchone()
                nums = extract(c.text)
                with conn.cursor() as cur:
                    cur.executemany("insert into chunk_numbers (chunk_id, raw, value, unit, scale) "
                                    "values (%s, %s, %s, %s, %s)",
                                    [(chunk_id, n.raw, n.value, n.unit, n.scale) for n in nums])
                stats["numbers"] += len(nums)
        stats["documents"] += 1
        stats["chunks"] += len(chunks)
        stats["tokens"] += sum(c.tokens for c in chunks)
        log(f"ingested {r['symbol']} {r['fiscal_label']}: {len(chunks)} chunks")

    totals = conn.execute("""select (select count(*) from documents), (select count(*) from chunks),
                                    (select count(*) from chunk_numbers),
                                    (select sum(pg_total_relation_size(c.oid)) from pg_class c
                                     join pg_namespace n on n.oid = c.relnamespace
                                     where n.nspname = 'quantrag' and c.relkind in ('r', 'm'))""").fetchone()
    avg = stats["tokens"] / stats["chunks"] if stats["chunks"] else 0
    log(f"this run: {stats['documents']} documents, {stats['chunks']} chunks (avg {avg:.0f} tokens), "
        f"{stats['numbers']} numbers")
    log(f"database: {totals[0]} documents, {totals[1]} chunks, {totals[2]} numbers, "
        f"schema size {totals[3] / 2**20:.1f} MB")
    return stats


def dry_run(manifest, raw_dir):
    embedder = Embedder()
    print(f"{'document':20} {'chunks':>6} {'avg tok':>7} {'median':>6} {'max':>4} {'<50 tok':>7} {'numbers':>7}")
    for r in cm.read_manifest(manifest):
        if r["filename"] and (Path(raw_dir) / r["filename"]).is_file():
            chunks = chunk_turns(parse_transcript(Path(raw_dir) / r["filename"]), embedder.count)
            t = [c.tokens for c in chunks]
            nums = sum(len(extract(c.text)) for c in chunks)
            print(f"{r['symbol'] + ' ' + r['fiscal_label']:20} {len(t):6} {statistics.mean(t):7.0f} "
                  f"{statistics.median(t):6.0f} {max(t):4} {sum(x < 50 for x in t):7} {nums:7}")


def main():
    if "--dry-run" in sys.argv:
        return dry_run(ROOT / "data/manifest.csv", ROOT / "data/raw")
    url = os.environ.get("SUPABASE_DB_URL")
    if not url:
        sys.exit("SUPABASE_DB_URL is not set (see .env.example)")
    with psycopg.connect(url, options="-c search_path=quantrag,public,extensions") as conn:
        ingest(conn, ROOT / "data/manifest.csv", ROOT / "data/companies.yaml", ROOT / "data/raw")


if __name__ == "__main__":
    main()
