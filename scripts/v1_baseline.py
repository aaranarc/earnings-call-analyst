"""Phase 0: v1 memory/latency baseline. Run against an extracted copy of tag v1-final:

    git archive v1-final | tar -x -C /tmp/v1copy
    python scripts/v1_baseline.py --v1-dir /tmp/v1copy --mode deployed
    python scripts/v1_baseline.py --v1-dir /tmp/v1copy --mode rerank

deployed: v1 as shipped (reranker disabled): embed + Chroma + Gemini answer, 10 questions.
rerank:   v1's original local CrossEncoder (the OOM config): retrieve 15 -> rerank -> top 5.
          Reuses query embeddings cached by `deployed`, so it makes no API calls and
          measures retrieval + rerank only (no generation).
Each mode runs in its own process so peak RSS is not shared. Each run appends to --out["runs"][mode];
repeat the rerank mode (free) to see the spread, since macOS RSS readings vary a lot between runs.
"""
import argparse
import json
import os
import platform
import resource
import statistics
import sys
import time
from importlib.metadata import version
from pathlib import Path

import psutil

QUESTIONS = [
    "What drove growth for Microsoft Cloud in Q1 2024?",
    "How did Apple's services revenue perform in Q1 2024?",
    "Compare the performance of Reliance Jio and O2C margins in Q1 2024.",
    "What did JPMorgan say about investment banking fees in Q1 2024?",
    "How did HDFC perform regarding credit risk and provisions?",
    "What was JPMorgan's net interest income guidance for 2024?",
    "Compare JPMorgan and HDFC on deposit growth.",
    "What did Infosys say about large deal wins?",
    "How did JPMorgan describe credit card net charge-offs?",
    "What is Infosys's revenue growth guidance for the year?",
]
RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"  # v1's model, from git history


def peak_rss_mb():
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024  # bytes on macOS, KB on Linux


def pct(xs, p):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, round(p / 100 * (len(xs) - 1)))]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1-dir", required=True)
    ap.add_argument("--mode", choices=["deployed", "rerank"], required=True)
    ap.add_argument("--out", default="eval/results/v1_baseline.json")
    a = ap.parse_args()
    repo = os.getcwd()
    out = os.path.abspath(a.out)
    out_p = Path(out)
    cache = Path(out.replace(".json", "_query_embeddings.json"))

    from dotenv import load_dotenv
    load_dotenv(os.path.join(repo, ".env"))
    os.chdir(a.v1_dir)
    sys.path.insert(0, os.path.abspath(a.v1_dir))
    from app.services.rag_service import RAGService

    svc = RAGService()
    row = {"mode": a.mode, "questions": len(QUESTIONS)}

    if a.mode == "deployed":
        row["startup_rss_mb"] = round(psutil.Process().memory_info().rss / 2**20, 1)
        lat, embs = [], {}
        for q in QUESTIONS:
            t = time.perf_counter()
            res = svc.ask(q)
            lat.append(time.perf_counter() - t)
            embs[q] = svc.embeddings.embed_query(q)  # cache for `rerank` mode; outside the timed block
            print(f"{lat[-1]:6.2f}s  {q[:55]:55}  -> {str(res.get('answer'))[:70]!r}")
        cache.write_text(json.dumps(embs))
        row["latency_scope"] = "ask(): embed query + Chroma + Gemini generation"
    else:
        embs = json.loads(cache.read_text())

        class Cached:  # stands in for Gemini embeddings: no API calls in this mode
            def embed_query(self, q):
                return embs[q]
        svc._embeddings = Cached()
        from sentence_transformers import CrossEncoder
        ce = CrossEncoder(RERANKER)
        row["startup_rss_mb"] = round(psutil.Process().memory_info().rss / 2**20, 1)
        lat = []
        for q in QUESTIONS:
            t = time.perf_counter()
            docs, _ = svc.retrieve_with_routing(q, n_results=15)
            if docs:
                ce.predict([[q, d] for d in docs])
            lat.append(time.perf_counter() - t)
        row["latency_scope"] = "retrieve 15 + CrossEncoder rerank (cached embeddings, no generation)"
        row["reranker"] = RERANKER

    row.update(
        peak_rss_mb=round(peak_rss_mb(), 1),
        p50_s=round(statistics.median(lat), 3),
        p95_s=round(pct(lat, 95), 3),
        latencies_s=[round(x, 3) for x in lat],
    )
    data = json.loads(out_p.read_text()) if out_p.exists() else {}
    data.setdefault("env", {}).update(
        python=platform.python_version(), machine=f"{platform.system()} {platform.machine()}",
        git_ref="v1-final",
        packages={p: version(p) for p in ["chromadb", "langchain-google-genai", "langchain-core", "torch", "sentence-transformers"]},
        note="Local laptop, unpinned v1 requirements resolved on run date. Not Render's 512 MB Linux box.",
    )
    data.setdefault("runs", {}).setdefault(a.mode, []).append(row)  # append: memory readings vary run to run
    out_p.write_text(json.dumps(data, indent=2))
    print(json.dumps({k: v for k, v in row.items() if k != "latencies_s"}, indent=2))


if __name__ == "__main__":
    main()
