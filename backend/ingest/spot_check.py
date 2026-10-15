"""Print a reproducible random sample of ingested data for a human spot-check.

    cd backend && SUPABASE_DB_URL=... python -m ingest.spot_check [--seed 42] [--chunks 3] [--numbers 20]

Shows N chunks per company (speaker, role, section, page, first 200 chars) and M stored numbers, each next to
the sentence it came from. Read-only. The same seed on the same data gives the same sample.
"""
import argparse
import os
import random
import re

import psycopg


def sentence_around(text, raw):
    i = text.find(raw)
    if i < 0:
        return text[:200]
    start = max(text.rfind(". ", 0, i) + 2, 0)
    end = text.find(". ", i + len(raw))
    return text[start:end + 1 if end >= 0 else len(text)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--chunks", type=int, default=3)
    ap.add_argument("--numbers", type=int, default=20)
    a = ap.parse_args()
    rng = random.Random(a.seed)
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        rows = conn.execute("""select co.symbol, d.fiscal_label, ch.id, ch.speaker, ch.role, ch.section, ch.page,
                                      ch.text from chunks ch join documents d on d.id = ch.document_id
                               join companies co on co.id = d.company_id order by ch.id""").fetchall()
        by_company = {}
        for r in rows:
            by_company.setdefault(f"{r[0]} {r[1]}", []).append(r)
        print(f"== {a.chunks} random chunks per document (seed {a.seed})")
        for doc, rs in sorted(by_company.items()):
            for r in sorted(rng.sample(rs, min(a.chunks, len(rs))), key=lambda r: r[2]):
                print(f"[{doc}] chunk {r[2]} · {r[3]} ({r[4]}, {r[5]}, p{r[6]})\n    {r[7][:200]!r}")
        nums = conn.execute("""select n.chunk_id, n.raw, n.value, n.unit, n.scale, ch.text, co.symbol
                               from chunk_numbers n join chunks ch on ch.id = n.chunk_id
                               join documents d on d.id = ch.document_id join companies co on co.id = d.company_id
                               order by n.chunk_id, n.raw, n.value""").fetchall()
        print(f"\n== {a.numbers} random numbers of {len(nums)} (seed {a.seed})")
        for i, (cid, raw, value, unit, scale, text, sym) in enumerate(rng.sample(nums, min(a.numbers, len(nums))), 1):
            sent = re.sub(r"\s+", " ", sentence_around(text, raw))
            print(f"{i:2}. [{sym} chunk {cid}] raw={raw!r} → value={value:g} unit={unit} scale={scale}\n    “{sent}”")


if __name__ == "__main__":
    main()
