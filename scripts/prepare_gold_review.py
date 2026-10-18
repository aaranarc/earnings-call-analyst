"""Create an UNREVIEWED evaluation draft from a read-only frozen database snapshot.

No answer generation or retrieval testing occurs. A person must check and edit questions,
answerability and exact supporting quotes before this can become eval/gold.jsonl.
Never sets human_verified=True and never reads the private numeric answer key.
"""
import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from itertools import combinations
from pathlib import Path

import psycopg

TOPICS = {"it_services": "operating margin", "private_bank": "net interest margin", "consumer": "EBITDA margin"}


def evidence(row):
    return {"symbol": row["symbol"], "fiscal_label": row["period"], "quotes": [row["text"]]}


def make_draft(records):
    """Draft 30 single-period, 15 peer, 10 across-period and 5 refusal questions."""
    candidates = []
    for row in sorted(records, key=lambda r: (r["period_end"], r["symbol"]), reverse=True):
        candidates.append(("single", f"What did {row['name']} report about {row['topic']} in {row['period']}?", [row]))
    singles = candidates[:30]
    peers, trends = [], []
    for a, b in combinations(records, 2):
        if a["sector"] == b["sector"] and a["period"] == b["period"] and a["symbol"] != b["symbol"]:
            peers.append(("comparison", f"Compare the {a['topic']} discussion at {a['name']} and {b['name']} in {a['period']}.", [a, b]))
        if a["symbol"] == b["symbol"] and b["ordinal"] - a["ordinal"] == 1:
            trends.append(("trend", f"How did the {a['topic']} discussion at {a['name']} change from {a['period']} to {b['period']}?", [a, b]))
    selected = singles + peers[:15] + trends[:10]
    if len(selected) != 55:
        raise ValueError("Insufficient distinct sourced records for the planned review packet")
    selected += [("refusal", question, []) for question in [
        "What did Microsoft's management report about Azure growth in Q1 FY27?",
        "What did Tesla report about automotive gross margin in Q2 2026?",
        "What did Apple say about iPhone revenue in Q3 2026?",
        "What will TCS's share price be exactly five years from today?",
        "What is the weather forecast for Mumbai tomorrow?",
    ]]
    items, notes = [], []
    for index, (kind, question, support) in enumerate(selected, 1):
        identifier = f"review-{index:02d}"
        items.append({"id": identifier, "question": question, "human_verified": False,
                      "reviewed_by": "", "answerable": bool(support), "evidence": [evidence(r) for r in support]})
        notes.append({"id": identifier, "category": kind, "sources": [
            {key: row[key] for key in ("symbol", "period", "speaker", "role", "page", "source_url", "sha256", "chunk_id")}
            for row in support]})
    if len({r["question"] for r in items}) != len(items):
        raise ValueError("Duplicate draft questions")
    return items, notes


def load_records(conn):
    raw = conn.execute("""select co.symbol, co.name, co.sector, d.fiscal_label, d.period_end, d.source_url,
        d.sha256, ch.id, ch.speaker, ch.role, ch.page, ch.text from chunks ch
        join documents d on d.id=ch.document_id join companies co on co.id=d.company_id
        where ch.role='management' and ch.section='prepared' order by d.period_end, co.symbol, ch.id""").fetchall()
    records = {}
    for symbol, name, sector, period, period_end, url, sha, chunk, speaker, role, page, text in raw:
        topic = TOPICS.get(sector)
        if not topic or topic not in text.lower() or "%" not in text:
            continue
        key = (symbol, period)
        records.setdefault(key, {"symbol": symbol, "name": name, "sector": sector, "topic": topic,
                                "period": period, "period_end": str(period_end), "source_url": url,
                                "sha256": sha, "chunk_id": chunk, "speaker": speaker, "role": role,
                                "page": page, "text": text,
                                "ordinal": int(period[-2:]) * 4 + int(period[1])})
    return list(records.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("Choose a new output directory; review material must not be overwritten")
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        conn.execute("set transaction isolation level repeatable read read only")
        records = load_records(conn)
        corpus = conn.execute("""select co.symbol,d.fiscal_label,d.sha256 from documents d
            join companies co on co.id=d.company_id order by co.symbol,d.fiscal_label""").fetchall()
        items, notes = make_draft(records)
    data = "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    args.out_dir.mkdir(parents=True)
    (args.out_dir / "gold-draft.jsonl").write_text(data)
    (args.out_dir / "review-sources.json").write_text(json.dumps({
        "status": "unreviewed_draft", "created_at": datetime.now(UTC).isoformat(),
        "draft_sha256": hashlib.sha256(data.encode()).hexdigest(), "corpus": corpus, "items": notes}, indent=2))
    (args.out_dir / "READ_ME.md").write_text("""# Human review required

These 60 questions are template-generated candidates, not a verified benchmark.
No system answers, retrieval scores or private numeric answer keys were consulted.

1. Open each PDF/page in review-sources.json and verify the company, fiscal period, speaker and quoted metric.
2. Edit the question and supporting quote(s). Check accounting basis, quarter vs annual values and whether the
   proposed evidence fully answers the question. Add evidence for omitted facts; remove unsuitable questions.
3. For comparisons, confirm both passages use comparable metrics and reporting bases. Differences in discussion
   are not proof of a causal change. The template itself does not establish comparability.
4. Verify refusal questions against the complete frozen corpus, not only the listed examples.
5. Only after your own review, set human_verified to true and enter your reviewer name for each row.
6. Save the reviewed set as eval/gold.jsonl and run the validation command in docs/EVALUATION.md.

Keep at least 60 distinct, reviewed questions and preserve the frozen corpus hashes. Do not tune retrieval on
this set after approval. Split tuning questions from the final held-out set if any tuning becomes necessary.
The 120 blind number labels are separate and were not opened, changed or regenerated by this tool.
""")
    print(f"Created {len(items)} UNREVIEWED candidates in {args.out_dir}")


if __name__ == "__main__":
    main()
