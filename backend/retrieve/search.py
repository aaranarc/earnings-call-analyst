"""Hybrid retrieval over quantrag.chunks.

    dense (pgvector cosine) ─┐
                             ├─ rrf ─ top 10 ─ rerank (cross-encoder) ─ top n
    fts (Postgres keyword) ──┘

Every hit carries its rank and score from each stage, for the UI's "How this was answered" panel.
Comparison questions (2+ companies) retrieve per company and keep top_n each, so one company can't crowd out
the other.
"""
from dataclasses import dataclass, field

EMBED_MODEL = "BAAI/bge-small-en-v1.5"          # must match ingest (vector(384))
RERANK_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"  # v1's reranker, as ONNX (D20)
RRF_K = 60

SELECT = """select ch.id, co.symbol, co.name, d.fiscal_label, ch.speaker, ch.role, ch.section, ch.page, ch.text,
                   {score} as score
            from chunks ch join documents d on d.id = ch.document_id join companies co on co.id = d.company_id
            where {where}
              and (%(companies)s::text[] is null or co.symbol = any(%(companies)s))
              and (%(periods)s::text[] is null or d.fiscal_label = any(%(periods)s))
            order by {order} limit %(k)s"""


@dataclass
class Hit:
    chunk_id: int
    symbol: str
    company: str
    fiscal_label: str
    speaker: str
    role: str
    section: str
    page: int
    text: str
    scores: dict = field(default_factory=dict)  # dense, dense_rank, fts, fts_rank, rrf, rrf_rank, rerank, rerank_rank


class Models:
    """Loaded once (at API startup in Phase 7). The reranker is optional because it's the memory-heavy part."""

    def __init__(self, rerank=True, rerank_batch=4, rerank_max_tokens=384):  # D23: peak RSS ≤ 512 MB
        from fastembed import TextEmbedding
        self.embedder = TextEmbedding(EMBED_MODEL)
        self.reranker = None
        self.rerank_batch = rerank_batch  # passages scored per ONNX call; drives peak memory (D20)
        if rerank:
            from fastembed.rerank.cross_encoder import TextCrossEncoder
            self.reranker = TextCrossEncoder(RERANK_MODEL)
            # question + passage are truncated together to this many tokens
            self.reranker.model.tokenizer.enable_truncation(max_length=rerank_max_tokens)

    def embed_query(self, query):
        return next(iter(self.embedder.query_embed(query)))


def _run(conn, sql_parts, params, stage):
    rows = conn.execute(SELECT.format(**sql_parts), params).fetchall()
    hits = []
    for rank, r in enumerate(rows, start=1):
        h = Hit(*r[:9])
        h.scores[stage], h.scores[f"{stage}_rank"] = float(r[9]), rank
        hits.append(h)
    return hits


def dense(conn, qvec, companies=None, periods=None, k=30):
    params = {"q": qvec, "companies": companies, "periods": periods, "k": k}
    return _run(conn, {"score": "1 - (ch.embedding <=> %(q)s)", "where": "true", "order": "ch.embedding <=> %(q)s"},
                params, "dense")


def fts(conn, query, companies=None, periods=None, k=30):
    # OR semantics: any query term may match (websearch_to_tsquery alone ANDs every word of a question, D22).
    # ts_rank_cd still orders by how many terms match and how close together. It is not BM25; see LEARNING.md
    tsq = "replace(websearch_to_tsquery('english', %(query)s)::text, '&', '|')::tsquery"
    params = {"query": query, "companies": companies, "periods": periods, "k": k}
    return _run(conn, {"score": f"ts_rank_cd(ch.tsv, {tsq})", "where": f"ch.tsv @@ {tsq}", "order": "score desc"},
                params, "fts")


def rrf(lists, k=RRF_K):
    """Reciprocal rank fusion: score(chunk) = sum over lists of 1 / (k + rank). Merges per-stage scores."""
    merged = {}
    for hits in lists:
        for rank, h in enumerate(hits, start=1):
            m = merged.setdefault(h.chunk_id, h)
            if m is not h:
                m.scores.update(h.scores)
            m.scores["rrf"] = m.scores.get("rrf", 0.0) + 1.0 / (k + rank)
    out = sorted(merged.values(), key=lambda h: -h.scores["rrf"])
    for rank, h in enumerate(out, start=1):
        h.scores["rrf_rank"] = rank
    return out


def rerank_text(h):
    """Same "company quarter · speaker (role): text" form the chunk was embedded with (D15)."""
    return f"{h.company} {h.fiscal_label} · {h.speaker} ({h.role}): {h.text}"


def rerank(models, query, hits, top_n):
    scores = list(models.reranker.rerank(query, [rerank_text(h) for h in hits], batch_size=models.rerank_batch))
    for h, s in zip(hits, scores):
        h.scores["rerank"] = float(s)
    out = sorted(hits, key=lambda h: -h.scores["rerank"])
    for rank, h in enumerate(out, start=1):
        h.scores["rerank_rank"] = rank
    return out[:top_n]


def _one(conn, models, query, qvec, companies, periods, mode, use_rerank, k, fuse_top, top_n):
    lists = []
    if mode in ("dense", "hybrid"):
        lists.append(dense(conn, qvec, companies, periods, k))
    if mode in ("fts", "hybrid"):
        lists.append(fts(conn, query, companies, periods, k))
    fused = rrf(lists)
    if use_rerank and models.reranker and fused:
        return rerank(models, query, fused[:fuse_top], top_n)
    return fused[:top_n]


def retrieve(conn, models, query, companies=None, periods=None, mode="hybrid", use_rerank=True,
             k=30, fuse_top=10, top_n=5, per_company_n=6, split_by_company=True):  # fuse_top: candidates reranked (D23)
    """mode: dense | fts | hybrid. By default, 2+ companies retrieve per company.

    split_by_company=False returns a single global ranking for retrieval evaluation."""
    qvec = models.embed_query(query) if mode != "fts" else None
    if split_by_company and companies and len(companies) > 1:
        # ponytail: per-company queries run sequentially on one connection; use a pool if latency matters (Phase 7)
        return [h for c in companies
                for h in _one(conn, models, query, qvec, [c], periods, mode, use_rerank, k, fuse_top, per_company_n)]
    return _one(conn, models, query, qvec, companies, periods, mode, use_rerank, k, fuse_top, top_n)
