"""Retrieval smoke test: recall@5 on 10 hand-written questions (eval/smoke.jsonl), before any tuning.

    cd backend && SUPABASE_DB_URL=... python ../eval/smoke_retrieval.py --rerank       # 6 configs, reranker loaded
    cd backend && SUPABASE_DB_URL=... python ../eval/smoke_retrieval.py --no-rerank    # 3 configs, no reranker

A question counts as a hit if any of its top-5 chunks belongs to the expected document and contains one of its
`quotes`. No company/period filters: the router (Phase 4) isn't built, so this measures raw retrieval.
Each invocation is its own process, so peak RSS reflects exactly the models it loaded. Results are appended to
eval/results/smoke_retrieval.json.
"""
import argparse
import json
import os
import platform
import resource
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

import psutil
import psycopg
from pgvector.psycopg import register_vector

from retrieve.search import EMBED_MODEL, RERANK_MODEL, Models, retrieve


def peak_rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024


def is_hit(h, item):
    return h.symbol == item["symbol"] and h.fiscal_label == item["fiscal_label"] and \
        any(q in h.text for q in item["quotes"])


def main():
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--rerank", action="store_true")
    g.add_argument("--no-rerank", action="store_true")
    ap.add_argument("--out", default=str(ROOT / "eval/results/smoke_retrieval.json"))
    a = ap.parse_args()
    items = [json.loads(line) for line in (ROOT / "eval/smoke.jsonl").read_text().splitlines() if line.strip()]

    models = Models(rerank=a.rerank)
    startup_rss = psutil.Process().memory_info().rss / 2**20
    configs = [(m, r) for r in ([False, True] if a.rerank else [False]) for m in ("dense", "fts", "hybrid")]
    results = {}
    with psycopg.connect(os.environ["SUPABASE_DB_URL"], options="-c search_path=quantrag,public,extensions") as conn:
        register_vector(conn)
        for item in items:  # every expected chunk must exist, or the smoke set is wrong
            n = conn.execute("""select count(*) from chunks ch join documents d on d.id = ch.document_id
                                join companies co on co.id = d.company_id where co.symbol = %s
                                and d.fiscal_label = %s and ch.text like any(%s)""",
                             (item["symbol"], item["fiscal_label"], [f"%{q}%" for q in item["quotes"]])).fetchone()[0]
            assert n >= 1, f"{item['id']}: no chunk contains its quotes"
        for mode, rr in configs:
            name = f"{mode}{' + rerank' if rr else ''}"
            per_q, lat = {}, []
            for item in items:
                t = time.perf_counter()
                hits = retrieve(conn, models, item["question"], mode=mode, use_rerank=rr, top_n=5)
                lat.append(time.perf_counter() - t)
                ranks = [i for i, h in enumerate(hits, 1) if is_hit(h, item)]
                per_q[item["id"]] = ranks[0] if ranks else None
            hit = sum(r is not None for r in per_q.values())
            results[name] = {"recall_at_5": hit / len(items), "hits": hit, "of": len(items),
                             "rank_of_expected": per_q, "p50_s": round(statistics.median(lat), 4),
                             "max_s": round(max(lat), 4)}
            print(f"{name:16} recall@5 {hit}/{len(items)}  p50 {statistics.median(lat) * 1000:6.1f} ms  "
                  f"ranks {per_q}")

    run = {"reranker_loaded": a.rerank, "startup_rss_mb": round(startup_rss, 1), "peak_rss_mb": round(peak_rss_mb(), 1),
           "embed_model": EMBED_MODEL, "rerank_model": RERANK_MODEL if a.rerank else None,
           "git_sha": subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True,
                                     cwd=ROOT).stdout.strip(),
           "machine": f"{platform.system()} {platform.machine()}", "python": platform.python_version(),
           "configs": results}
    print(f"peak RSS {run['peak_rss_mb']} MB (reranker {'loaded' if a.rerank else 'not loaded'})")
    out = Path(a.out)
    data = json.loads(out.read_text()) if out.exists() else {"runs": []}
    data["runs"].append(run)
    out.write_text(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
