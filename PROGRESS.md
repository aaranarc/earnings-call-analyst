# QuantRAG v2: Progress

## Status
- Phase 0 (audit and setup): **done**.
- **Phase 1 (corpus): tooling done. Waiting on Aarana's manual downloads.** Gates (D12): `phase2` 0/3 sectors · `A` 0/48 · `B` 0/96.
- Branch `v2`. v1 is frozen at tag `v1-final` (commit `80174a8` on `main`).

## The v1 baseline is for a tiny corpus (read before comparing v1 and v2)
v1's data folder held 9 PDFs, but **only 6 were real transcripts** (JPMorgan, HDFC and Infosys, two quarters each). The other 3 (Apple, Microsoft, Reliance) were one-line placeholders. The shipped index held just **one** real transcript (JPMorgan Q2 2024, 88 chunks). So v1's memory and latency figures describe a system answering over roughly one transcript, and v2's quality numbers have **no v1 equivalent** to compare against. Any "v1 → v2" claim must say this. Only the reranker memory story (peak RAM with and without the PyTorch reranker) is a like-for-like comparison.

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
- Of v1's real PDFs, only Infosys Q2 FY25 is inside the Phase 1 window (D8).
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

## Cleanup candidates (ask before deleting)
Done in Phase 1 (D11): untracked scratch files and `* 2` duplicates moved to `../quantrag_v1_scratch/`, `venv/` deleted.
Tracked v1 files to remove later in v2: `app/scripts/ingest.py`, `app/resave_model.py 22-34-15-124.py`, `app/services/resave_model copy.py`, `app/services/resave_model.py`, `resave_model.py`, `scratch.py`, `app/test_service.py`, `chroma_db/`, `models/`, the `.DS_Store` files.

## Phase 1: corpus
### Done (Claude Code)
- `data/companies.yaml`: the 12 companies (NSE symbol, name, sector, aliases). Aliases are checked to be unique across companies.
- `data/manifest.csv`: all 96 expected rows (12 × Q2 FY25 → Q1 FY27), with `symbol`, `fiscal_label` and `period_end` pre-filled.
- `scripts/check_manifest.py`: checks every filled row (known symbol, label in window, `period_end` matches the label, call within 120 days after quarter end, https `source_url`, file exists, sha256 matches, no duplicate quarter or PDF). It lists pending rows, absent rows and unreferenced PDFs. `--fill-sha` computes hashes so nobody types them. Reports three gates (D12) and exits 1 if `--gate` (default `B`) fails or any row has an error.
- `scripts/test_check_manifest.py`: 27 tests, all passing. Ruff is clean.
- 1 row partly filled: **INFY Q2 FY25** (v1's real PDF, call date 2024-10-17 from its cover page, sha filled). Its `source_url` is **empty and flagged**, because the download link isn't recorded anywhere. Find it and fill it in, or replace the PDF with a fresh download.
- Housekeeping: `venv/` deleted; scratch files, `* 2` duplicates and the old v1 data moved to `../quantrag_v1_scratch/`; `git fetch --refetch` restored the missing blob (`git fsck` is clean), and the restored blob was scanned for keys with 0 hits, so the history scan now covers everything.

### Aarana's checklist (manual, per brief: no scripting against NSE)
1. For each pending row, download the earnings-call transcript PDF from the company's investor-relations page or its BSE/NSE corporate announcement ("Earnings Call Transcript").
2. Save it as `data/raw/{SYMBOL}_Q{n}FY{yy}.pdf` (for example `TCS_Q3FY26.pdf`).
3. In `data/manifest.csv` fill in `call_date` (from the cover page, YYYY-MM-DD), `source_url` (the exact PDF link) and `filename`. Leave `sha256` empty.
4. Run `.venv/bin/python scripts/check_manifest.py --fill-sha` and fix anything it reports.
5. **Pick rows by the quarter's end date, not the cover's label.** For example, a cover saying "Q1 FY'24" was a July 2023 call. Nestlé India in particular may label its quarters differently around its change of financial year (D9).
6. If a site blocks access or a transcript doesn't exist, **leave the row pending** and note it here. Don't use mirrors.
7. To excuse a row that can't be obtained: add it to `EXCUSED` in `scripts/check_manifest.py` **and** log the evidence under D12 in `docs/DECISIONS.md`. At most 6.
- **Done when (D12):** `--gate phase2` passes → Phase 2 can start · `--gate A` passes → the latest 4 quarters are complete · `--gate B` passes → Phase 1 is done.
- **Suggested order:** first one transcript per sector (unlocks Phase 2), then the latest 4 quarters for all 12 (Tier A), then the older 4 (Tier B).

### Next: Phase 2 (DB and ingestion)
Starts when `python scripts/check_manifest.py --gate phase2` passes: one real transcript per sector.

## Open questions
1. **Nestlé India coverage is unverified.** Aarana asked: if BSE lists fewer than 6 Nestlé transcripts in the window, propose an FMCG replacement. BSE returned **HTTP 403** to an automated fetch of the Nestlé announcements page (scrip 500790) on 2026-10-15, so per brief rule 4 the check stopped there. No workaround was tried. Needs a manual count by Aarana on BSE (or approval to check Nestlé India's own investor-relations page instead). No replacement is proposed until the count is known.
2. Untracked root `asset.png` is byte-identical to the committed `assets/asset.png`. It's safe to delete; left alone until approved.
3. Still open from brief §11: Cloud Run vs Render (#3) and PDF storage for the weekly job (#4). Both are needed by Phase 9.

## Resolved
- Window → D8. Repo layout → D7. Missing git blob → restored with `git fetch --refetch`, `fsck` clean.
- `main` diverged from GitHub → `origin/main` merged into `main` (clean: README + assets only). Pushed `main`, tag `v1-final` and `v2` on 2026-10-15, after a key scan of the outgoing commits found nothing.
- "Why 90 of 96" → D12.
- Infosys Q2 FY25 `source_url` → Aarana is adding the BSE link.
