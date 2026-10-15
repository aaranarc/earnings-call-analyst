"""Validate human-reviewed gold data and run retrieval ablations without generation.

See docs/EVALUATION.md for the schema, commands, and metric definitions.
"""
import argparse
import hashlib
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def load_gold(path):
    items, ids, questions = [], set(), set()
    for line_no, line in enumerate(Path(path).read_text().splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            require(isinstance(item, dict), "row must be an object")
            for key in ("id", "question", "reviewed_by"):
                require(isinstance(item.get(key), str) and item[key].strip(), f"missing {key}")
            require(item.get("human_verified") is True, "human verification required")
            require(type(item.get("answerable")) is bool, "answerable must be a boolean")
            require(item["id"] not in ids, "duplicate id")
            question = " ".join(item["question"].lower().split())
            require(question not in questions, "duplicate question")
            evidence = item.get("evidence")
            require(isinstance(evidence, list), "evidence must be a list")
            require(bool(evidence) == item["answerable"], "answerability and evidence disagree")
            seen = set()
            for e in evidence:
                require(isinstance(e, dict), "evidence must be an object")
                for key in ("symbol", "fiscal_label"):
                    require(isinstance(e.get(key), str) and e[key].strip(), f"missing evidence {key}")
                quotes = e.get("quotes")
                require(isinstance(quotes, list) and quotes, "quotes must be a nonempty list")
                require(all(isinstance(q, str) and q.strip() for q in quotes), "empty quote")
                signature = (e["symbol"], e["fiscal_label"], tuple(sorted(quotes)))
                require(signature not in seen, "duplicate evidence item")
                seen.add(signature)
            ids.add(item["id"])
            questions.add(question)
            items.append(item)
        except (AssertionError, ValueError, TypeError) as exc:
            raise ValueError(f"gold line {line_no}: {exc}") from exc
    if not items:
        raise ValueError("gold set is empty")
    return items


def matches(hit, evidence):
    return (hit.symbol == evidence["symbol"] and hit.fiscal_label == evidence["fiscal_label"]
            and any(q in hit.text for q in evidence["quotes"]))


def score(item, hits):
    """Quotes within one evidence item are alternatives; separate items are all required."""
    ranks = [next((i for i, h in enumerate(hits[:10], 1) if matches(h, e)), None)
             for e in item["evidence"]]
    first = min((r for r in ranks if r is not None), default=None)
    return {"evidence_ranks": ranks,
            "hit_at_5": bool(first is not None and first <= 5) if ranks else None,
            "mrr_at_10": 1 / first if first else (0.0 if ranks else None),
            "completeness_at_5": sum(r is not None and r <= 5 for r in ranks) / len(ranks) if ranks else None}


def summarize(rows):
    answerable = [r for r in rows if r["hit_at_5"] is not None]
    return {"questions": len(rows), "answerable_questions": len(answerable),
            **{key: statistics.mean(r[key] for r in answerable) if answerable else None
               for key in ("hit_at_5", "mrr_at_10", "completeness_at_5")},
            "p50_s": statistics.median(r["elapsed_s"] for r in rows)}


def validate_corpus(conn, items):
    # Literal substring matching, not SQL LIKE: '%' and '_' in gold quotes aren't wildcards.
    for item in items:
        for evidence in item["evidence"]:
            texts = conn.execute(
                """select ch.text from chunks ch join documents d on d.id=ch.document_id
                   join companies co on co.id=d.company_id
                   where co.symbol=%s and d.fiscal_label=%s""",
                (evidence["symbol"], evidence["fiscal_label"])).fetchall()
            if not any(q in text for (text,) in texts for q in evidence["quotes"]):
                raise ValueError(f"{item['id']}: required evidence absent from corpus")


def run_config(conn, models, items, companies, latest, mode, rerank, router):
    from generate.router import route
    from retrieve.search import retrieve

    rows = []
    for item in items:
        start = time.perf_counter()
        rt = route(item["question"], companies, latest, enabled=router)
        # Evaluate one global ranked list: comparison fan-out would otherwise yield >k hits,
        # concatenated by company, which isn't a global ranking suitable for MRR.
        hits = [] if rt.kind == "out_of_scope" else retrieve(
            conn, models, item["question"], companies=rt.companies or None, periods=rt.periods or None,
            mode=mode, use_rerank=rerank, top_n=10, split_by_company=False)
        rows.append({"id": item["id"], **score(item, hits),
                     "chunk_ids": [h.chunk_id for h in hits], "elapsed_s": time.perf_counter() - start,
                     "route_kind": rt.kind})
    return {"summary": summarize(rows), "rows": rows}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gold", type=Path, required=True)
    parser.add_argument("--validate-only", action="store_true", help="offline schema check; no DB/model calls")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--rerank", action="store_true", help="also run reranker ablations")
    args = parser.parse_args()
    gold_bytes = args.gold.read_bytes()
    items = load_gold(args.gold)
    if args.validate_only:
        print(f"Validated {len(items)} human-reviewed questions (schema only).")
        return
    if args.out is None:
        parser.error("--out is required for a run")
    if args.out.exists():
        parser.error("output already exists; choose a new path to preserve previous runs")

    import psycopg
    from pgvector.psycopg import register_vector

    import check_manifest as cm
    from generate.answer import latest_periods
    from retrieve.search import EMBED_MODEL, RERANK_MODEL, Models

    with psycopg.connect(os.environ["SUPABASE_DB_URL"],
                         options="-c search_path=quantrag,public,extensions") as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        register_vector(conn)
        validate_corpus(conn, items)
        corpus = conn.execute("select symbol, fiscal_label, sha256 from documents "
                              "join companies on companies.id=documents.company_id "
                              "order by symbol, fiscal_label").fetchall()
        companies, _ = cm.load_companies(ROOT / "data/companies.yaml")
        latest = latest_periods(conn)
        models = Models(rerank=args.rerank)
        configs = {}
        for router in (False, True):
            for rerank in ((False, True) if args.rerank else (False,)):
                for mode in ("dense", "fts", "hybrid"):
                    key = f"{mode}:rerank={rerank}:router={router}"
                    configs[key] = run_config(conn, models, items, companies, latest, mode, rerank, router)
                    print(key, json.dumps(configs[key]["summary"]))
    if args.gold.read_bytes() != gold_bytes:
        raise ValueError("gold file changed during evaluation; results were not written")
    result = {"created_at": datetime.now(UTC).isoformat(),
              "git_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
              "gold_sha256": hashlib.sha256(gold_bytes).hexdigest(),
              "corpus": corpus, "embed_model": EMBED_MODEL,
              "rerank_model": RERANK_MODEL if args.rerank else None,
              "settings": {"ranking": "global", "candidate_k": 30, "fuse_top": 10, "top_n": 10,
                           "rerank_batch": 4, "rerank_max_tokens": 384},
              "configs": configs}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x") as out:
        json.dump(result, out, indent=2)
        out.write("\n")


if __name__ == "__main__":
    main()
