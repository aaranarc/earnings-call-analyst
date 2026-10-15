# QuantRAG v2: Progress

## Status
- **Phase 0 (audit and setup): done, waiting for Aarana's approval to start Phase 1.**
- Branch `v2`. v1 is frozen at tag `v1-final` (commit `80174a8` on `main`).

## Phase 0: v1 audit

### What each v1 module does
| Module | What it does | v2 fate |
|---|---|---|
| `app/main.py` | FastAPI: `POST /ask`, `GET /companies`, `POST /risk-score`, `GET /health/memory`. Errors return the full Python traceback to the client. | Replaced in Phase 7. Keep the idea of the memory endpoint (psutil RSS). Stop leaking tracebacks. |
| `app/services/rag_service.py` | `RAGService`: Chroma `PersistentClient` (or `HttpClient` if `CHROMA_HOST`), Gemini chat, Gemini embeddings (lazy). Router: company names matched as substrings of the question; ≥2 matches → one filtered query per company, splitting `n_results`. Reranker property returns `None`. Answer prompt: plain f-string with "say I don't have enough information". | Router idea is reused and rebuilt with aliases and rules (Phase 4). Everything else is replaced. |
| `RAGService.predict_risk` | Taiwan-bankruptcy XGBoost + RobustScaler + winsorising. Features without data are filled with a constant `0.45–0.54`, chosen by **a hash of the company name**. 4 features are mapped from yfinance. SHAP top-3, then a RAG call for "context". | Removed. Replaced by the EWS API (Phase 10). |
| `app/ui/streamlit_app.py` | Streamlit UI (Bloomberg style): chat, company list, risk gauge. Before the `v1-final` WIP commit, the SHAP panel showed **hard-coded** percentages (34% / 28% / 15%). | Replaced by Next.js (Phase 8). |
| `re_ingest.py` (now committed) | The ingest that built the shipped index: deletes `chroma_db/`, PyMuPDF per page, 1000-char/200-overlap splitter, Gemini embeddings (3072-d). Filename parsing puts the market into `quarter` (`parts[1]`) and ignores the real quarter, so Q1 and Q2 of one company get **identical chunk IDs** (`{company}_{quarter}_{year}_{i}`). Errors are caught and only printed. | Replaced by `backend/ingest/` (Phase 2). |
| `app/scripts/ingest.py` | Older ingest: MiniLM embeddings (384-d) into a Chroma server. **Doesn't match** the Gemini query embeddings, so it is dead code. | Delete (needs approval). |
| `app/scripts/evaluate_rag.py` | 5 hand-written questions; Gemini judges Gemini (faithfulness, context precision). **Crashes**: calls `rag.reranker.predict` while `reranker` is `None`. The ground truths paraphrase the synthetic stub PDFs (below). | Replaced by `eval/` (Phase 6). Accurate wording: "v1 had a 5-question self-judged eval that no longer runs". |
| `models/` | XGBoost model + scaler + bounds + feature names. | Removed with the risk score. |
| `chroma_db/` (committed) | 91 chunks: **88 from JPMorgan Q2 only, 1 each from the Apple/Microsoft/Reliance stubs, 0 HDFC, 0 Infosys, 0 JPMorgan Q1.** | Replaced by pgvector (Phase 2). |
| `render.yaml`, `compose.yaml`, `Dockerfile`, `build.sh` | 2 Render services (API + Streamlit). Compose runs a Chroma server. The Dockerfile copies the whole repo into the image. | Replaced by Cloud Run + Vercel (Phase 9). |
| `notebooks/` | Ingestion and retrieval sandbox notebooks. | Not used in v2. |

### Findings to keep in mind (honesty items)
1. **The Apple, Microsoft and Reliance "transcripts" are synthetic one-line stubs** (~130 characters, ~1.5 KB PDFs), not real calls. Only 6 PDFs are real: JPMorgan Q1/Q2 2024, HDFC Q1/Q2 2024, Infosys Q1/Q2 2024.
2. Deployed v1 effectively covered **one real transcript: JPMorgan Q2 2024**. JPMorgan Q1 is missing, consistent with the ID collision. The HDFC and Infosys PDFs exist locally but never made it into the index; the cause isn't recorded, because `re_ingest.py` swallows errors.
3. Part of v1's risk score is driven by a hash of the company name, not by data. Don't present it as a model output in interviews.
4. v1 *did* have an eval script, but it was self-judged, had 5 questions, and is now broken.

### What v2 reuses
- The router *concept* (per-company filtered retrieval for comparisons), rebuilt with `companies.yaml` aliases.
- The memory-endpoint idea, as `peak RSS` in the eval harness and `/health`.
- The real HDFC and Infosys PDFs, only if they fall inside the Phase 1 window (see open questions).
- Nothing else in v1 code is reused directly.

## v1 baselines ("before" figures)
Source: `eval/results/v1_baseline.json`, produced by `scripts/v1_baseline.py` against `git archive v1-final`. Exact package versions: `eval/results/v1_baseline_freeze.txt`.

| Configuration | Runs | Peak RSS | p50 | p95 | What latency covers |
|---|---|---|---|---|---|
| v1 as deployed (reranker off) | 1 | 171.8 MB | 1.657 s | 2.127 s | embed + Chroma + Gemini answer |
| v1 + local CrossEncoder (`ms-marco-MiniLM-L-6-v2`, the OOM config) | 5 | **511.7–691.7 MB** (median 614.8) | 0.067–0.085 s | 0.144–1.358 s | retrieve 15 + rerank, no generation |

Caveats: measured on a macOS arm64 laptop (Python 3.11.15), not Render's Linux box. v1's requirements are unpinned, so they resolved to the versions available on the run date. macOS memory readings are noisy: across the 5 reranker runs, startup RSS ranged from 118 to 574 MB, so startup RSS isn't reported as a baseline. The deployed row is a single run, kept to the approved Gemini quota. Every reranker run peaked **at or above Render free's 512 MB limit**, which matches the v1 OOM story; the deployed config peaked about 3–4× lower. The reranker p95 is dominated by first-call warm-up. 6 of the 10 deployed answers were refusals ("I don't have enough information"), because the index barely covers anything beyond JPMorgan.

## Decisions confirmed by Aarana
- Company list: the 12 from the brief (IT services, private banks, consumer).
- Drop the US PDFs (and the synthetic stubs).
- Tag after committing the WIP v1 edits plus `re_ingest.py` (done).

## Cleanup candidates (not touched: ask before deleting)
Untracked: `.env 2` (contains keys; git-ignored now), `.gitignore 2`, `Dockerfile 2`, `README 2.md`, `requirements 2.txt`, `asset.png`, `test_cohere.py`, `test_dns_patch.py`, `test_endpoints.py`, `test_gemini.py`, `test_hf_api.py`, `test_jpm.py`, `test_models.py`, `test_response.py`, `test_urllib3_patch.py`, plus the broken local `venv/` (points to a removed Anaconda Python).
Tracked v1 files to remove later in v2: `app/scripts/ingest.py`, `app/resave_model.py 22-34-15-124.py`, `app/services/resave_model copy.py`, `app/services/resave_model.py`, `resave_model.py`, `scratch.py`, `app/test_service.py`, `chroma_db/`, `models/`, the `.DS_Store` files.

## Next: Phase 1 (corpus)
- **Aarana:** manually download about 96 transcripts (12 companies × last 8 quarters) into `data/raw/` and fill in `data/manifest.csv`.
- **Claude Code:** `data/companies.yaml`, the `data/manifest.csv` header, `scripts/check_manifest.py` (file exists, sha256 matches, fiscal_label ↔ period_end consistent), plus tests.

## Open questions
1. **Which 8 quarters?** As of 2026-10-15, the latest likely reported quarter is Q2 FY27 (Jul–Sep 2026), and not all 12 companies will have reported it yet. My proposal: the window is Q3 FY25 → Q2 FY27, with "latest available" per company. The existing 2024 HDFC/Infosys PDFs (labelled "2024 Q1/Q2", probably Q4 FY24/Q1 FY25) would fall outside it.
2. **Corrupt local git object:** one old blob of `chroma_db/chroma.sqlite3` is missing (`git fsck` reports `missing blob 5b4d89d…`). The current tree is fine. `git fetch origin` may restore it. Harmless for v2, but fix before any history rewrite.
3. **Repo layout:** the brief shows a `quantrag/` root. I propose `backend/` and `frontend/` directly at this repo's root (it is already the QuantRAG repo).
4. Still open from brief §11: Cloud Run vs Render (#3) and PDF storage for the weekly job (#4). Both are needed by Phase 9.
