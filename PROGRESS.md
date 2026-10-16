# QuantRAG v2: Progress

## Current release status · 2026-10-16
- Core ingestion, retrieval, cited answers, number checking, API, dashboard and research storage are implemented.
- Verified corpus: **40 official transcripts across 7 Indian companies**, plus 2 separately registered HDFC results releases. Latest-four coverage is 25/48; full planned window is 40/96. Remaining coverage is not complete.
- Growth Payoff is deployed: 4 reviewed investment projects, 9 sourced milestones, operational progress chart and a 3/5-year assumption explorer. It does not claim a validated company forecast or automatic coverage of all projects.
- QuarterLens and Follow-through retain source quotes, reporting bases, missing-period handling and unresolved evidence saving.
- Phase 6 evaluation tooling is implemented. Human-reviewed gold questions, blind number labels, judge calibration and published benchmark scores remain pending. The owner deferred the 120 labels and Nestlé count.
- Published on existing free [Vercel frontend](https://quantrag.vercel.app/growth-payoff) and [Render API](https://quantrag-api.onrender.com/health), from release commit `1dac325`. [Main CI](https://github.com/aaranarc/earnings-call-analyst/actions/runs/38924279612) passed. Verified the live source drawer, scenario controls, 375px layout, expanded corpus snapshot, API health and out-of-scope refusal.
- Release smoke-test limitation: cited-answer generation reached Gemini but the provider returned HTTP 503 UNAVAILABLE (high demand). A successful live generated answer was not verified in this release check; retry when provider availability recovers. Dashboard evidence and scenarios remain available independently.
- Bankruptcy/EWS integration and Telegram are outside the current release scope. No new paid hosting is authorized.
- The chronological phase notes below are historical development records, not the current completion checklist.

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

## Phase 2: DB and ingestion
### Done
- `db/schema.sql`: the brief's schema in `quantrag`, idempotent, plus a unique `(company, quarter)` on documents and lookup indexes.
- `backend/ingest/parse.py`: PDF → page text → headers/footers removed → speaker turns with role (management / analyst / moderator) and section (prepared / qa) → boilerplate dropped. Handles both "Name: text" and name-on-its-own-line layouts.
- `backend/ingest/chunk.py`: one speaker per chunk, ≤450 tokens, sentence split with 1-sentence overlap. `backend/ingest/run.py`: manifest → parse → chunk → fastembed `BAAI/bge-small-en-v1.5` → DB, one transaction per document, skip by sha256, logs counts, average tokens and schema size.
- `backend/numcheck/extract.py`: number extraction + normalisation, pulled forward from Phase 5 (D13).
- Tests: 57 backend tests (38 number extraction, 7 parsing including the 4 real transcripts, 6 chunking, 3 DB). **All 57 pass** when `TEST_DATABASE_URL` points at the local container (otherwise the 3 DB tests skip). Plus 27 checker tests. Ruff is clean.
- Pinned deps in `backend/pyproject.toml`. `.env.example` has key names only.

### Measured on the 4 transcripts on disk: `cd backend && python -m ingest.run --dry-run` (no DB)
| Transcript | Chunks | Avg tokens | Median | Max | Chunks under 50 tokens | Numbers |
|---|---|---|---|---|---|---|
| TCS Q1 FY27 | 69 | 124 | 91 | 434 | 21 | 85 |
| HDFC Bank Q1 FY27 | 62 | 175 | 132 | 445 | 13 | 136 |
| HUL Q1 FY27 | 72 | 139 | 114 | 440 | 16 | 87 |
| Infosys Q2 FY25 | 84 | 105 | 85 | 446 | 24 | 111 |
Chunks are far below the brief's ~350–500 tokens (D14).

### Local Postgres run (2026-10-15)
Container: `docker run -d --name qr-pg -e POSTGRES_PASSWORD=pg -p 127.0.0.1:5433:5432 pgvector/pgvector:pg17` (Postgres 17.11, pgvector 0.8.7). Stop with `docker stop qr-pg`.
- `TEST_DATABASE_URL=postgresql://postgres:pg@localhost:5433/postgres pytest tests/test_ingest_db.py`: **3 passed**, including the second-run-adds-nothing test.
- Real pipeline (`SUPABASE_DB_URL` set to the local container, `python -m ingest.run`, twice):
  - run 1: 4 documents, **287 chunks (avg 133 tokens)**, 419 numbers; `quantrag` schema **2.0 MB**
  - run 2: "4 already ingested · 0 to ingest", totals unchanged (**idempotent on real data**)
  - Per document: TCS 69 chunks / 14 speakers · INFY 84 / 17 · HDFCBANK 62 / 11 · HINDUNILVR 72 / 9
- Rough sizing: ~0.5 MB per transcript locally → 96 transcripts ≈ 50 MB, well inside Supabase free's 500 MB. To be confirmed on Supabase.

### Spot-check before Supabase (2026-10-15), local DB, `cd backend && python -m ingest.spot_check`
Labels below are my (Claude Code's) manual judgments on a reproducible random sample. **Right** = a real quantity, with the value, unit and scale as the speaker meant them.

**Chunks (seed 42, 3 per document): 12 of 12 have the correct speaker, role and section.**
| Document | Chunk: speaker (role, section, page) | Verdict |
|---|---|---|
| HDFCBANK Q1 FY27 | Sashidhar Jagdishan (management, prepared, p2) · Srinivasan Vaidyanathan (management, qa, p4) · Srinivasan Vaidyanathan (management, qa, p12) | ✅ ✅ ✅ |
| HINDUNILVR Q1 FY27 | Nihal Jham (analyst, qa, p14) · Priya Nair (management, qa, p14) · Yogesh Mulgaonkar (management, qa, p15; reading out collected investor questions) | ✅ ✅ ✅ |
| INFY Q2 FY25 | Bryan Bergin (analyst, qa, p9) · Jonathan Lee (analyst, qa, p10) · Prashant Kothari (analyst, qa, p21) | ✅ ✅ ✅ |
| TCS Q1 FY27 | Nehal Shah (management, prepared, p2) · Sudeep Kunnumal (management, prepared, p7) · Gaurav Rateria (analyst, qa, p21) | ✅ ✅ ✅ |
Notes, not mis-tags: the Nehal Shah chunk keeps one leftover disclaimer sentence ("We have outlined these risks in the second slide…"; the safe-harbour filter drops only sentences with its keywords). The Prashant Kothari chunk is only pleasantries ("Okay. All right. Thank you very much."), see D17.

**Numbers (20 random each round):**
| Round | Extractor state | Stored numbers | Right | Precision | Wrong ones |
|---|---|---|---|---|---|
| 1 (seed 42) | as built in Phase 2 | 419 | 16/20 | **80%** | `360` (360-degree), `50` (Fortune 50), `6` (list marker "6."), `00` (5:00 PM) |
| 2 (seed 42, new data) | + skip times, X-degree compounds, index names, list markers | 386 | 17/20 | **85%** | `4` (S/4HANA), `27` (full year '27), `40` in "40, 50 basis points" (value right, unit missing) |
| 3 (seed 7) | + skip numbers fused to letters or after ' / ’ | 368 | 18/20 | **90%** | `11` in "11 odd percent" (value right, unit missing), `3` in "stage 3 assets" (a label) |

Each fix came with regression tests (`backend/tests/test_numbers.py`, now 45 cases), and local ingest was re-run after each (`truncate` on the local container only).
- **Known remaining misses:** a unit written once for a list ("40, 50 basis points"), "N odd percent", and category labels ("stage 3"). Left for Phase 5: the matcher can compare values when a stored number has no unit. The Phase 5 checker evaluation (~100 hand-labelled numbers, `eval/numbers_gold.jsonl`) is the real measurement. These 20-number samples are small (one wrong = 5 points).
- After the fixes: 4 documents, 287 chunks (avg 133 tokens), **368 numbers**, schema 2.0 MB on local Postgres.

### Supabase run (2026-10-15)
Project `cjttcgxtmgcpvzqtzzkg` (Mumbai `ap-south-1`, session pooler, port 5432), Postgres 17.11, pgvector 0.8.2. `cd backend && python -m ingest.run` with `SUPABASE_DB_URL` from `.env`, run twice:
- run 1: 4 documents, **287 chunks (avg 133 tokens)**, 368 numbers; `quantrag` schema **2.0 MB**
- run 2: "4 already ingested · 0 to ingest", totals unchanged (**idempotent on Supabase**)
- Whole database: **13 MB of the 500 MB free tier** (Supabase's built-in `auth`/`storage`/`realtime`/`vault` schemas plus `quantrag`).
- The schema-wiping DB tests were **not** run against Supabase (they refuse non-localhost URLs).

### Phase 2 done-condition: met for the current corpus
All complete manifest rows ingested ✅ · re-run adds 0 rows ✅ (local and Supabase) · speaker-parsing tests on real transcripts ✅ · idempotency test ✅ · chunk count, avg tokens and DB size logged ✅. The corpus itself is still 4 of 96 (Phase 1 gates A and B).

## Phase 3: Retrieval
### Done
- `backend/retrieve/search.py`: `dense` (pgvector cosine) · `fts` (`websearch_to_tsquery` + `ts_rank_cd`, as the brief specifies) · `rrf` (k=60) · `rerank` (fastembed `Xenova/ms-marco-MiniLM-L-6-v2`, top 20 fused → top n) · per-company retrieval for 2+ companies (top 6 each). Every hit keeps rank and score from each stage.
- CLI: `cd backend && python -m retrieve "question" [--company TCS] [--period "Q1 FY27"] [--mode dense|fts|hybrid] [--no-rerank]`.
- `backend/tests/test_retrieve.py`: RRF on a hand-worked example (3 tests). Backend total: 64 pass, 3 DB tests skip without `TEST_DATABASE_URL`.

### Smoke set
`eval/smoke.jsonl`: **20 hand-written questions, 5 per company**. Several quote exact figures (₹72,275 crore, INR2,731 crores, 85.9%, 60 basis points) to test keyword search. Expected chunk = right document + contains a hand-picked quote (all verified to exist). No company filter (router not built), local Postgres, 3 runs per setting in separate processes. Raw results: `eval/results/smoke_retrieval.json`; the first 10-question untuned run is kept in `smoke_retrieval_10q_untuned.json`. Labels are mine; s05 was widened after seeing results (D21). **Aarana to review.**

### Tuning log (one change at a time; details in DECISIONS)
| Step | Change | hybrid recall@5 | hybrid+rerank recall@5 | Peak RSS (reranker on) | Decision |
|---|---|---|---|---|---|
| 0 | untuned, 20 questions | 14/20 | 19/20 | 1,118–1,183 MB | — |
| — | s05 palm oil | — | — | — | not an ingest bug; label too narrow (D21) |
| 1 | keyword OR semantics | **19/20** | 18/20 | 1,116–1,191 MB | kept (D22) |
| 2a | reranker batch 8, 384 tokens | 19/20 | 18/20 | 468–599 MB | rejected (>512 once) |
| 2a | batch 4, 256 tokens | 19/20 | 17/20 | 399–426 MB | rejected (recall lower) |
| 2a | batch 4, 384 tokens | 19/20 | 18/20 | 374–516 MB (6 runs) | rejected (>512 once) |
| 2b | + rerank top 10 instead of 20 | 19/20 | 18/20 | **386–419 MB (6 runs)** | **kept (D23)** |
| 2c | smaller cross-encoder | — | — | — | n/a: already MiniLM-L-6 |

### Final: all six configurations, 20 questions, shipped defaults (3 runs)
| Configuration | recall@5 | p50 latency | Misses |
|---|---|---|---|
| vector only | 14/20 | 5–6 ms | s01 s04 s08 s12 s14 s20 |
| keyword only (OR) | 15/20 | ~2 ms | s02 s08 s13 s18 s19 |
| **hybrid (RRF)** | **19/20** | **~7 ms** | s08 |
| vector + rerank | 15/20 | 338–356 ms | s01 s08 s12 s14 s20 |
| keyword + rerank | 17/20 | 425–446 ms | s02 s08 s12 |
| hybrid + rerank | 18/20 | 429–463 ms | s08 s12 |

| Process | Peak RSS (3 runs) |
|---|---|
| reranker not loaded | 274–285 MB |
| reranker loaded and used | 410–419 MB (386–419 MB over 6 runs) |
| v1 for comparison | 172 MB without reranker · 512–692 MB with PyTorch reranker |

**Takeaways:** (1) keyword OR + vector via RRF is the biggest win: 14 → 19/20 with no model cost. (2) Reranker memory is now under 512 MB, with ~90 MB headroom on macOS, down from ~1.1 GB, so the v1 OOM story has a measured fix. (3) **On this small set the reranker no longer adds recall** (hybrid 19 vs hybrid+rerank 18) and costs ~0.44 s. Whether to keep it is a Phase 6 ablation on the full gold set. (4) s08 (Infosys tax rate) is missed by every hybrid configuration. Worth a look when the gold set exists.

## Phase 4: Router and generation
### Done
- `backend/generate/router.py`: rule-based router (D26). `backend/generate/answer.py`: route → retrieve (router's company/period filters) → numbered excerpts → Gemini structured output → citation validation → answer or refusal (D27). CLI: `cd backend && python -m generate "question"`.
- Tests: `test_router.py` (24) and `test_answer.py` (10, fake LLM, no API calls). Backend total **98 pass**, 3 DB tests skip without `TEST_DATABASE_URL`. Ruff clean.
- Pinned: `langchain-core 1.6.10`, `langchain-google-genai 4.4.2`, `pydantic 2.14.1`, `psutil 7.2.2`. `.env.example` lists `GEMINI_API_KEY`, `GEMINI_MODEL`, `ROUTER_ENABLED`, `REFUSAL_MIN_RERANK`.

### Done-check: `eval/phase4_check.py` (local DB, `GEMINI_MODEL=gemini-3.1-flash-lite`, results in `eval/results/phase4_check.json`)
| Set | Result | What "pass" means |
|---|---|---|
| 10 answerable (8 smoke questions + 2 comparisons) | **10/10** | not refused · ≥1 citation · cites only the companies asked about · cites a chunk containing the expected evidence (each company, for comparisons) |
| 3 unanswerable | **3/3 refused** | Wipro (not ingested) and TCS Q3 FY26 (quarter not ingested) refused before any LLM call; HUL share-price target refused by the model |
| 1 out of scope ("weather in Mumbai") | **1/1 refused** | no retrieval, no LLM call; lists covered companies |
Typical answer time ≈ 2.4 s (retrieve ≈ 0.45 s with reranker + Gemini ≈ 2 s). ~11 Gemini calls per run.

**My read of all 14 outputs (not automated):** answers 1–8 and 10 are faithful to their cited excerpts, and refusals list what's available. Issues found: (1) the model added tables to single-company answers; fixed in code (D27) and re-run. (2) The TCS vs Infosys comparison labels TCS's **total** TCV as "Large Deal TCV"; kept as a known failure for the Phase 6 report. (3) "$2.4 bn" was rewritten as "$2.4 billion" (same value).

## Pre-Phase 5: CI, secrets hook, router report, model pin (D28–D30)
- **CI:** test and coverage results are available in [GitHub Actions](https://github.com/aaranarc/earnings-call-analyst/actions/workflows/ci.yml?query=branch%3Amain).
- **gitleaks pre-push hook:** blocks pushes with findings; fails closed without gitleaks; install steps in README.
- **Router:** 17/20 fully correct on 20 new labelled queries (companies 90%, periods 95%, intent 90%). Smoke hybrid+rerank recall@5 18 → 19/20 with the router on.
- **Model:** `.env.example` pins `GEMINI_MODEL=gemini-3.1-flash-lite` (stable). Final choice on the gold set.
- **Local tests now use `quantrag_test`,** never the dev database (D28 incident).
- **Known failure kept for Phase 6:** TCS total TCV labelled "Large Deal TCV" (D27).

## Phase 5: Number checker
### Done
- `backend/numcheck/match.py`: `verified` / `found_elsewhere` / `derived` (formula) / `unverified` per number, using the citations in the number's own sentence (D31). Wired into `generate/answer.py`: every answer now has `numbers[]` (where, raw, value, unit, status, offsets, formula, source chunk). Table cells are checked against their own citations.
- Extractor: stated precision (`decimals`) and a `pp` unit. Stored numbers unchanged (0 rows differ), so no re-ingest.
- Tests: **67 number tests** (45 extraction + 22 matching: every format in the brief, precision, units, signs, ranges, sentence-level citations, derivations, made-up numbers) against the brief's ≥ 25. Full suite locally: **153 passed** (incl. DB tests on `quantrag_test`).
- Labelling sheet: `eval/numbers_label.py` → 37 real answers (saved in `eval/private/`) → **120 rows: 77 real + 33 value corruptions + 10 context swaps**, shuffled under ids `n001…` (D32, D34). The answer key is only in git-ignored `eval/private/numcheck_key.json` (D33).
- Labelling page: `python eval/label_server.py`, then open http://127.0.0.1:8765. Local only. One row at a time, number highlighted in the sentence, same-value numbers highlighted in the excerpts; keys 1/2/3 = supported / not supported / unsure; saves after every click to `eval/labels/numbers_labels.csv`. Checked: listens on 127.0.0.1 only, rejects bad labels, never sends key fields, renders correctly (headless-Chrome screenshot).
- Scoring: `python eval/numbers_eval.py`: red and any-flag precision/recall for real / corrupted / all, plus recall per corruption type. Partial results stay in `eval/private/` until every row is labelled.

### Not done (needs Aarana)
- **Label the 120 rows** with the page. Phase 5's done-condition (checker metrics in `eval/results/`) needs this. The guide is on the page (click "Labelling guide").
- **Don't open** `eval/private/` or the old `eval/results/numcheck_answers.json` from commit `efa92f7` until done (D33).
- **Expect** context swaps to pass as `verified`; that's the known limitation of value-based checking (D34).

### Found while generating answers
- **Phase 6 failure case (kept): a12 "What was TCS's cash conversion as a share of net income?" was refused**, though chunk 585 says "Our cash conversion remained strong at 93% of net income." It was also a smoke-set retrieval miss (s12). A real failure case for the Phase 6 report.
- a30 (A&P as a share of turnover) and a31 (per-branch % increase) were refused because they need a calculation the prompt forbids. That's the intended behaviour (D27).

## Open questions
0. **INFY Q2 FY25 `source_url` set on Aarana's verification, 2026-10-15.** infosys.com returns HTTP 403 to automated downloads (twice), so the tool couldn't compare hashes. Aarana confirmed the file at the URL has the same sha256 as `data/raw/INFY_Q2FY25.pdf` (`0c28ccd2…ce14a00`). Not re-checkable by script while the block stands.
1. **Nestlé India coverage is unverified.** Aarana asked: if BSE lists fewer than 6 Nestlé transcripts in the window, propose an FMCG replacement. BSE returned **HTTP 403** to an automated fetch of the Nestlé announcements page (scrip 500790) on 2026-10-15, so per brief rule 4 the check stopped there. No workaround was tried. Needs a manual count by Aarana on BSE (or approval to check Nestlé India's own investor-relations page instead). No replacement is proposed until the count is known.
3. Still open from brief §11: Cloud Run vs Render (#3) and PDF storage for the weekly job (#4). Both are needed by Phase 9.

## Resolved
- Window → D8. Repo layout → D7. Missing git blob → restored with `git fetch --refetch`, `fsck` clean.
- `main` diverged from GitHub → `origin/main` merged into `main` (clean: README + assets only). Pushed `main`, tag `v1-final` and `v2` on 2026-10-15, after a key scan of the outgoing commits found nothing.
- "Why 90 of 96" → D12.
- Infosys Q2 FY25 `source_url` → Aarana is adding the BSE link.

## Alpha freeze cleanup
- Untracked generated Python artifacts and ignored future coverage/build outputs; deleted the root image as requested.
- Removed static CI results and hand-written CI metrics; README links to live main CI, and CI runs for main pushes and PRs.
- Audited project and user MCP configurations: the project config already targets the ingestion project; no stale reference found in active user settings.

## Phase 6: retrieval evaluation tooling
- Added `eval/retrieval_eval.py`: offline human-review/schema checks, corpus evidence checks, dense/keyword/hybrid × router × optional reranker runs, and per-question evidence metrics with provenance.
- Added an opt-in global ranking mode for evaluation; production comparison fan-out remains the default.
- Usage and gold schema: `docs/EVALUATION.md`. No held-out gold set or benchmark results were created.
- Still needed: human-reviewed gold questions, generation/refusal scoring, cross-family judge and human agreement calibration, model comparison, ablations on gold, and the failure-case report. Phase 5 labels and Nestlé counting remain deferred to Aarana.

## Dashboard-first product slice
- Implemented the supplied dark Geist/magenta/violet UI across landing, thesis workspace, Ask, Eval and pipeline pages.
- Added local persistence, thesis evidence comparison, manual assessments, export, source drawers, inline number checks, comparison tables, retrieval traces, and saving cited answers into a thesis.
- Added local FastAPI endpoints and Next.js proxy. Confirmed a live cited answer with number checks against the configured corpus.
- Automated browser tests cover mobile widths, evidence transfer, persistence and accessibility. Public evaluation results remain pending.
- Automatic cross-quarter thesis extraction/matching, production authentication/deployment and complete Phase 6 judging remain unbuilt. Telegram, Nestlé counting and number labels remain deferred.

## Visual research workspace refresh
- Replaced the magenta/violet glow with charcoal panels, neutral typography and a restrained pale-lime accent, following the supplied Qenora and visual-report references.
- Added an API-backed company/quarter coverage map, clickable manual-assessment breakdown, evidence progress markers, and a printable research brief preserving saved source references.
- Shortened landing and thesis cards; Ask exposes citation and number-match counts without inventing financial time series.
- Still local: deployment follows evaluation/guardrail work and production access/usage controls. Phase 5 labels, reviewed gold questions and Nestlé coverage remain outstanding; automated thesis matching is not implemented.

## Research workflow hardening
- Evidence timeline is append-only, supports any number of periods up to storage validation limits, and preserves the original two notes through v1 migration. Adding new evidence resets manual assessment/review.
- Added validated JSON import with preview, conflict-safe merge and export/restore; original v1 storage remains available for recovery.
- Number-match wording no longer implies claim verification; cited sources show Q&A/prepared metadata and adjacent stored excerpts.
- Missing requested company/period coverage now refuses before retrieval. Mixed-period comparisons carry a visible warning.
- Coverage sourcing blocked by HTTP 403 on official PDF downloads. See `data/source_candidates.json` for verified source locations; corpus remains unchanged. Full Gate A is 48 transcripts across all 12 companies, not just the four-company demo subset.
- Remaining: obtain/validate PDFs and expand overlap; human-reviewed Phase 6 gold set and generation/judge calibration; source-backed automated thesis suggestions; deployment usage controls/hosting. Labels and Nestlé count remain deferred.

## Release implementation status (supersedes earlier remaining-work notes)
- Added on-demand thesis checking: selected company/period retrieval → conservative model suggestion → exact-quote/period validation → reviewable evidence. Saving appends source quotes and keeps the final assessment manual.
- Added generation/refusal evaluator, explicit cross-family judge adapter, human-agreement calculation and guarded public-report publication. No human gold, calibration result or benchmark number has been invented.
- Added production-only server token enforcement, bounded server-side Next proxy, atomic daily request reservations, generation timeouts/output limits, API/web images, Compose preview and deployment runbook. Replaced the old v1 Render configuration.
- Live check confirmed source-backed TCS suggestions while assessment remained unresolved; a missing-quarter comparison refused with no retrieved context.
- Hosting selection is explicitly deferred by the owner until release checks. Official PDF downloads remain blocked by 403; reviewed gold questions, independent human calibration, deferred number labels and Nestlé count remain real data/review dependencies.
- Background scheduled ingest, automatic status changes, Telegram and optional distress API are not part of this on-demand dashboard release.

## Public free deployment (supersedes hosting deferral)
- Owner chose free deployment tonight and confirmed the Render workspace “aarana's supabase”.
- Dashboard: https://quantrag.vercel.app (Vercel Hobby). API: https://quantrag-api.onrender.com (Render Free). No paid resources provisioned.
- Coverage/eval snapshots ship with the web deployment so browsing stays available while the API sleeps. Live model requests wake the API.
- Vercel was deployed using source files; GitHub integration and automatic redeploys are not configured. Render also uses explicit deployments. See docs/DEPLOYMENT.md.
- Corpus expansion, human-reviewed gold/calibration, the deferred number labels and Nestlé count remain data/review work; public benchmark scores remain pending.

## Router follow-up: sectors and latest available quarter
- Rechecked the four official PDF candidates: direct downloads still return HTTP 403. The old local HDFC PDFs are FY24, outside the frozen Q2 FY25–Q1 FY27 corpus window. No coverage or public snapshot was inflated.
- Router recognizes bank/banking, IT-services/company and FMCG/consumer sector queries when no company is named; all configured peers remain required by the coverage guard. Partial sector data cannot silently produce a market-wide winner.
- Added this/latest/most-recent quarter wording, resolved from ingested periods rather than today's calendar. Explicit fiscal periods take precedence over relative wording. Ranking words such as best/highest/strongest select comparison intent.
- New regression checks cover routing and the generation coverage boundary. The original 20 inspected development queries pass; this is a regression check, not a new held-out accuracy result. The original router report is preserved as historical evidence.
- Coverage expansion and human-reviewed evaluation remain pending; the deferred 120 labels and Nestlé count were not touched.

## Eight-transcript corpus expansion (supersedes the four PDF download blockers)
- Owner supplied official TCS Q2/Q3/Q4 FY26 and Infosys Q2 FY26 PDFs. Verified company, period, call date, page structure and SHA-256; recorded source URLs and hashes in the manifest. Original downloads preserved; raw PDFs remain ignored by Git.
- Parsing retains management/analyst roles and prepared/Q&A sections; new chunks stay within 450 tokens. Ingested the four documents into the approved Supabase project using the authenticated connector after the local PostgreSQL network connection timed out. Each document uses one atomic statement.
- Verified 8 documents, 581 chunks, 847 numbers and complete 384-dimensional embeddings. Original document IDs/hashes/counts preserved. Repeating every import added zero documents/chunks/numbers. Provenance: eval/results/coverage_expansion.json.
- TCS now has Q2 FY26 through Q1 FY27; Infosys has Q2 FY25 and Q2 FY26. Same-quarter TCS/Infosys Q2 FY26 comparison and four-quarter TCS research are now possible. Latest-four gate is only 7/48; total coverage is 8/96, so neither full coverage gate is claimed complete.
- Refreshed API and bundled web coverage snapshots. Historical four-transcript development metrics remain labeled historical; public human-reviewed benchmark metrics remain pending.

## Company-first quarterly change dashboard
- Added favourite company tiles, a clickable operating-margin chart with missing-quarter slots and explicit one-off exclusions, latest company-reported movement cards, and a management commentary timeline. Quotes retain speaker, physical PDF page, official URL and PDF hash.
- Deterministic extraction uses management prepared remarks, rejects conflicting/annual/guidance values, and never computes a quarter-on-quarter comparison across missing periods. Arithmetic agreement is separate from accounting-basis review.
- Signals save idempotently to the existing local research store as unresolved evidence. Existing notes/import/export remain available at `/research`; `/watchlist` is the new company dashboard. Corrupt local storage is preserved rather than overwritten.
- Monitor snapshots build after verified PDF ingestion and ship with the frontend so viewing them does not wake the API. CI checks manifest provenance and bundled snapshot parity.
- This slice does not classify missed commitments or prove that commentary caused results. Broader metrics, India/US coverage, longitudinal commitment matching and validated business-performance scenarios remain future work. Human-reviewed evaluation and the owner's deferred labels/Nestlé count remain outstanding.

## Follow-through pilot
- Made the product focus visible on the landing page and first QuarterLens feature panel: earlier announcement → later management report → sourced result → saved evidence.
- Rule-based salary-increase matching links consecutive calls only, with two actual TCS sequences. Explicit previous-quarter references are distinguished from topic matches needing review. Negation, future completion claims, analyst statements and wrong-quarter references are rejected.
- The pilot keeps wage-only impact separate from net margin movement. Every trail includes original quotes/pages/PDF hashes; saving preserves all sources and leaves assessment unresolved. Other companies show a no-linked-evidence state.
- This is a narrow pilot, not broad commitment tracking or an independently verified causal/missed-promise classifier. Competitive products already support cross-quarter research; differentiation still requires user validation and stronger data coverage.

## Quarterly coverage and result depth
- Expanded the approved Supabase corpus to 40 official transcripts across seven companies: HCLTech/Wipro/HUL eight quarters each, Infosys/ICICI Bank five each, TCS four and HDFC Bank two. Latest-four gate is 25/48; full window is 40/96. No US coverage is claimed.
- Verified source brands, periods, call dates, PDF hashes and management/prepared metadata. Preserved the original eight documents. Database now has 2,700 chunks and 5,676 numbers, all with non-null 384-dimensional embeddings. Local reparse text hashes and extracted-number counts match every stored document. Three representative replays added no rows. See `eval/results/coverage_expansion_40.json`.
- Added ICICI-style opening-remark parsing without treating financial subheadings as speakers. Added a quarter selector for every registered call, sector-appropriate margin series and distinct states for missing transcripts versus an unextracted figure.
- Added a separate registry for two HDFC earnings releases; their total-assets NIM figures are not mixed with interest-earning-assets NIM. Consumer consolidated/standalone and adjusted/reported figures remain distinct. Reported ranges retain both bounds without a synthetic midpoint.
- Change cards label calculations from adjacent as-reported figures separately from management-reported movements. Missing periods and incompatible/adjusted bases do not create automatic comparisons. Follow-through stays a reviewable salary-topic pilot, with no company rating or causal verdict.
- The dashboard is a sourced margin overview with linked calls/results, not a complete income-statement database. Remaining transcripts, US coverage, broader financial metrics and independently evaluated commitment matching remain further work; human gold/calibration and the owner's deferred labels/Nestlé count remain pending.
# Growth Payoff pilot · 2026-10-16

- Added `/growth-payoff`, linked from main navigation, landing CTA and QuarterLens. Charcoal/lime cards,
  clickable investment timelines, source drawer and a dashed scenario chart with adjustable 3/5-year horizon.
- Four reviewed projects: HUL Minimalist and premium-format capacity, HCLTech AI infrastructure, Wipro HARMAN DTS.
  Nine source milestones retain PDF hashes, physical pages, speakers and fiscal periods. Minimalist uses the
  reported ₹2,706 crore payout, not the earlier enterprise valuation. Planned capex and ceilings stay explicit.
- Source snapshot rebuild checks PDF hashes and unique prepared-management matches; CI validates registered
  provenance and reviewed project definitions. These are reviewed selectors, not general investment extraction.
- Scenario model calculates annual incremental operating profit from capital, assumed return, start delay and
  linear ramp. Negative returns and zero returns supported. No whole-company forecast, compounding, cash flow,
  stock target or accuracy claim. Entire capital assumed deployed at start; not a capital expenditure schedule.
- Saved project evidence uses existing unresolved research storage; scenarios do not become sourced facts.
- Remaining for company projections: comparable multi-year statements, project-attribution evidence, a
  sector-specific operating model, time-separated historical validation and calibrated uncertainty.
