# Decisions

One dated entry per meaningful decision. Never rewrite old entries; add a new entry that supersedes the old one.

---

## D1 · 2026-10-15 · Build v2 in this repo, on branch `v2`
- **Decided:** keep the existing repo (`aaranarc/earnings-call-analyst`). Freeze v1 at tag `v1-final`, build v2 on `v2`.
- **Options:** new repo · same repo with a branch.
- **Why:** keeps the history that tells the v1 → v2 story (the OOM fix, the reranker), and the brief requires not deleting v1.
- **Trade-off:** v1 and v2 files coexist on `v2` until the v1 files are removed with approval.
- **Revisit if:** the repo name or the old history becomes a liability for the public portfolio.

## D2 · 2026-10-15 · Commit the uncommitted v1 edits before tagging `v1-final`
- **Decided (Aarana):** commit the SHAP-factor edits (`rag_service.py`, `streamlit_app.py`, `requirements.txt`) plus `re_ingest.py` as `wip: v1 …`, then tag.
- **Options:** tag the last commit `8d17bb1` and leave the edits uncommitted · commit, then tag.
- **Why:** the tag should match the code that was actually being run, including the script that built the shipped index.
- **Trade-off:** `v1-final` contains WIP code. `build.sh`'s mode change (exec bit removed) was reverted, not committed, because it looked accidental.
- **Revisit if:** never; tags are immutable.

## D3 · 2026-10-15 · Ignore `.env*`, allow `.env.example`
- **Decided:** `.gitignore` now ignores `.env*` with an exception for `!.env.example`.
- **Why:** an untracked `.env 2` holding real keys was not ignored, so one `git add .` would have committed it. A history scan of every reachable blob (98) found only placeholders; no secrets were ever committed. One blob (an old `chroma.sqlite3`) is missing locally and couldn't be scanned. It's a binary vector DB, not config.
- **Trade-off:** none.
- **Revisit if:** a committed env template with a different name is ever needed.

## D4 · 2026-10-15 · How the v1 baseline is measured
- **Decided:** `scripts/v1_baseline.py` runs against `git archive v1-final` extracted to a temp dir, in a fresh Python 3.11 venv (matching v1's Dockerfile). One process per configuration. Peak = `getrusage(RUSAGE_SELF).ru_maxrss`; startup = psutil RSS after init.
  - `deployed`: v1 as shipped, 10 questions through `ask()` (10 Gemini answers + embeddings).
  - `rerank`: v1's original local `cross-encoder/ms-marco-MiniLM-L-6-v2` (sentence-transformers/PyTorch), retrieve 15 → rerank. It reuses the query embeddings cached by `deployed`, so it makes **no API calls** and has **no generation step**.
- **Options:** run in the repo working tree · run against an extracted copy.
- **Why an extracted copy:** opening the committed `chroma_db/` with today's chromadb modified the files in place (I restored them from git). An extracted copy keeps the repo untouched and can be re-run.
- **Trade-off:** v1's requirements are unpinned, so the baseline uses the versions resolved on 2026-10-15 (recorded in `eval/results/v1_baseline_freeze.txt`). Measured on a macOS arm64 laptop, not Render's 512 MB Linux box. The two rows' latencies cover different scopes and aren't directly comparable.
- **Repeats:** runs append to `runs[mode]`. The reranker row has 5 runs (peak 511.7–691.7 MB) because single readings varied by more than 100 MB. The deployed row has 1 run, to stay within the approved Gemini quota.
- **Revisit if:** we need Linux numbers. Then re-run the same script inside v1's Docker image.

## D5 · 2026-10-15 · No model-ID swap needed for the baseline
- **Decided:** run v1 unmodified.
- **Why:** Aarana allowed swapping only the model ID if it had been retired. On 2026-10-15 both `gemini-3.1-flash-lite` and `models/gemini-embedding-2` resolved via the Gemini models API.
- **Revisit if:** a re-run fails because a model was retired. Then swap only the ID and add a new entry here.

## D6 · 2026-10-15 · Corpus: the brief's 12 Indian companies; drop US and stub PDFs
- **Decided (Aarana):** TCS, Infosys, HCLTech, Wipro · HDFC Bank, ICICI Bank, Axis Bank, Kotak Mahindra Bank · Hindustan Unilever, ITC, Nestlé India, Asian Paints. Drop the US PDFs.
- **Why:** three sectors with four peers each make comparisons meaningful. The audit also found that the Apple/Microsoft/Reliance PDFs are synthetic one-line stubs, so they can't be in an honest corpus.
- **Trade-off:** loses JPMorgan, v1's only well-covered company.
- **Revisit if:** a legitimate source of US transcripts is added later.

## D7 · 2026-10-15 · `backend/` and `frontend/` at the repo root
- **Decided (Aarana):** no `quantrag/` wrapper folder. This repo *is* QuantRAG.
- **Why:** one less level of nesting, and nothing else lives in this repo.
- **Trade-off:** the v1 folders (`app/`, `models/`, `chroma_db/`) sit beside the v2 ones until they are removed with approval.
- **Revisit if:** never, unless the repo starts hosting a second project.

## D8 · 2026-10-15 · Corpus window: Q2 FY25 → Q1 FY27, the same 8 quarters for all 12 companies
- **Decided (Aarana):** fixed window, 12 × 8 = 96 expected transcripts. Q2 FY27 arrives later through the weekly ingest.
- **Options:** fixed window · "latest 8 available" per company.
- **Why fixed:** comparisons across companies line up quarter by quarter, and the gold set can name the same periods for every company.
- **Trade-off:** the newest quarter isn't in the starting corpus.
- **Applied:** of v1's real PDFs only Infosys Q2 FY25 is in the window (kept as `data/raw/INFY_Q2FY25.pdf`). HDFC Q1/Q2 FY24 and Infosys Q1 FY25 are outside it. v1's filenames mislabelled them ("HDFC 2024 Q1" is a July 2023 call). The JPMorgan PDFs, the three synthetic stubs and the out-of-window PDFs were moved to `../quantrag_v1_scratch/v1_data/`, not deleted.
- **Revisit if:** the window rolls forward (the weekly ingest adds new quarters, and `WINDOW` in `scripts/check_manifest.py` is then updated with a new entry here).

## D9 · 2026-10-15 · `fiscal_label` is our normalised April–March label, derived from `period_end`
- **Decided:** `fiscal_label` always follows the Indian April–March year (Q1 FY26 = Apr–Jun 2025, ending 2025-06-30), and `scripts/check_manifest.py` rejects any row whose `period_end` doesn't match its label.
- **Why:** companies label quarters inconsistently ("Q1 FY'24", "Q1 2024", calendar years). One rule, checked by code, means the router and the gold set can trust the label.
- **Trade-off:** our label can differ from the label printed on a company's PDF. **Nestlé India** in particular used a calendar financial year until it moved to April–March, so its PDFs from around that change may carry different quarter names. I'm not certain how Nestlé labelled the transition quarters, so pick its rows **by the quarter's end date**, not by the name on the cover.
- **Revisit if:** a covered company uses a non-March year end.

## D10 · 2026-10-15 · Phase 1 tooling: tests beside the script, a Python 3.11 dev venv, pinned deps in `backend/pyproject.toml`
- **Decided:** `scripts/test_check_manifest.py` sits next to the script it tests (pytest's default import mode puts that folder on the path, so no config is needed). Dev venv at `.venv/` (git-ignored) on Python 3.11, the only suitable local interpreter. Pinned: PyYAML 6.0.3, pytest 9.1.1, ruff 0.17.0.
- **Why:** the smallest setup that runs. `backend/pyproject.toml` is the brief's single pinned-deps file and grows in Phase 2.
- **Trade-off:** the brief targets a `python:3.12` image; local dev is 3.11 for now. Nothing in Phase 1 depends on the difference.
- **Revisit if:** Phase 2 adds anything that differs between 3.11 and 3.12. Then install 3.12 locally.

## D11 · 2026-10-15 · v1 scratch files moved out of the repo, not deleted
- **Decided (Aarana):** `venv/` deleted (broken). The untracked `test_*.py` scratch files and the `* 2` duplicates (including `.env 2`, which holds real keys) were moved to `../quantrag_v1_scratch/`.
- **Why:** keeps the repo clean without losing anything.
- **Revisit if:** never. Delete that folder by hand once it's no longer needed.

## D12 · 2026-10-15 · Corpus completion in gates: Phase 2 gate, Tier A, Tier B (≥90 of 96, excuses logged)
- **Why 90 of 96:** the brief sets "≥ 90 rows" for Phase 1. That leaves room for up to 6 transcripts (about 6%) that can't legitimately be obtained: a company that didn't hold or publish a call that quarter, a PDF missing from both the IR page and the exchange filing, or a source that blocks access (brief rule 4 forbids working around blocks). Requiring all 96 would let one unavailable PDF block the whole project. A much lower bar would leave comparisons with holes.
- **Rule:** a row may only fall short if it is **excused**: listed in `EXCUSED` in `scripts/check_manifest.py` with a reason **and** logged below with the evidence (what was checked, where, when). At most 6 rows (`MAX_EXCUSED`). Missing without an excuse fails Tier B, even with ≥90 complete.
- **Gates** (`python scripts/check_manifest.py --gate …`; any row error fails every gate):
  - `phase2`: ≥1 complete transcript per sector (3 sectors). Phase 2 (ingestion) may start, because speaker parsing is tested on 3 real transcripts, one per sector.
  - `A`: the latest 4 quarters (Q2 FY26 → Q1 FY27) complete for all 12 companies = 48 rows, **no excuses**. Recent quarters matter most for "last quarter / last two quarters" questions, and an analyst would expect them all.
  - `B`: the full window, 96 rows complete or excused, ≤6 excused. This is the brief's Phase 1 done-condition.
- **Options considered:** one flat "≥90 rows" count (doesn't say *which* rows are missing; 6 gaps could all be one company's recent quarters) · all 96 required (one unavailable PDF blocks the project) · tiers with logged excuses (chosen).
- **Trade-off:** the excuse list is maintained by hand in two places (code and this file). The tests pin the gate logic, not the list.
- **Revisit if:** more than 6 rows are genuinely unavailable. Then replace the company (see Nestlé, PROGRESS open question) rather than raising the cap.

### Excused rows
None yet.

## D13 · 2026-10-15 · Number extractor built in Phase 2, not Phase 5
- **Decided:** `backend/numcheck/extract.py` (find + normalise numbers) is built now. The matcher (verified / derived / unverified) stays in Phase 5.
- **Why:** Phase 2 ingestion must fill `chunk_numbers` "using the same numcheck extractor that Phase 5 uses". Building it later would mean re-ingesting everything, or a backfill step that idempotent ingest (skip by sha256) doesn't do.
- **Trade-off:** extractor changes in Phase 5 require re-ingesting (drop the documents and run again). Tolerable while the corpus is small.
- **Choices inside:** values are signed: an explicit minus or a nearby decline word ("down 130 bps") makes them negative. The Phase 5 matcher should fall back to absolute values when an answer drops the direction word. Years, Q/FY/H labels, dates and ordinals are skipped. A range ("20–22%") gives two numbers sharing one `raw`.
- **Revisit if:** the Phase 5 checker evaluation shows extraction misses (recall on `numbers_gold.jsonl`).

## D14 · 2026-10-15 · Chunks are single speaker turns, so they're much smaller than the brief's ~350–500 tokens
- **Measured (4 transcripts, `bge-small` tokenizer, `python -m ingest.run --dry-run`):** average 105–175 tokens per chunk, median 85–132, max 446. 13–24 chunks per call are under 50 tokens (e.g. "Got it. Thanks, and all the best.").
- **Why:** earnings-call Q&A is a rapid back-and-forth. The brief's two chunking rules conflict ("~350–500 tokens" vs "never mix two speakers"). I kept **never mix speakers** because each chunk then has exactly one speaker and role for citations, and long turns still split at 450 tokens.
- **Options:** (a) one turn per chunk (chosen) · (b) analyst question + management answer as one "exchange" chunk (mixes speakers; better context for short follow-ups) · (c) drop chunks under N tokens (loses short but factual answers like "Yes, 24%").
- **Mitigation:** each vector embeds a small header with company, quarter, speaker and role (D15), so a short follow-up still carries its context.
- **Revisit if:** Phase 6 hit-rate on Q&A-sourced gold questions is weak. Then run (b) as an ablation.

## D15 · 2026-10-15 · Embed "company quarter · speaker (role): text"; store raw text
- **Decided:** the vector is computed from `"{company name} {fiscal_label} · {speaker} ({role}): {chunk text}"`. `chunks.text` (and so the keyword index and citations) stays the raw transcript text.
- **Why:** a short turn like "And what about margins?" means nothing on its own. The header lets dense retrieval tie it to the company, quarter and speaker. The raw text keeps citations exact.
- **Trade-off:** changing the header format means re-embedding everything.
- **Revisit if:** the ablation shows the header doesn't help, or hurts.

## D16 · 2026-10-15 · Ingestion details
- **Only rows that pass `check_manifest.py` are ingested.** A row with an error (e.g. missing `source_url`) is reported and skipped, so every stored document has a source link for the citation drawer.
- **One transaction per document,** and skip if the `sha256` is already stored. Re-running is safe and adds 0 rows. A crash mid-document leaves nothing behind.
- **Text extraction:** pdfplumber per page; pypdf for pages where pdfplumber emits `(cid:N)` codes (TCS). Then Unicode NFKC (ligatures "ﬁ" → "fi", otherwise keyword search misses "financial") and one font-specific fix: pypdf renders TCS's "ff" ligature as "Ư" (checked: every occurrence is "ff").
- **Speaker roles:** moderator by name; analyst if the moderator introduces them ("question is from the line of X from Y"); management if named on the cover or if they speak before Q&A opens (TCS has no participant list). All speakers in the 4 test transcripts got a role, none `unknown`.
- **Boilerplate dropped:** moderator turns, labelled "Disclaimer:"/"Note:" blocks, sentences matching forward-looking / safe-harbour wording, turns under 5 words, running headers/footers (lines repeated at page edges on ≥50% of pages) and "Page N of M".
- **The DB test runs only against localhost** (`TEST_DATABASE_URL`), because it drops the `quantrag` schema.
- **Revisit if:** a new transcript layout breaks the speaker rules. Add it as a real-PDF test case first.

## D17 · 2026-10-15 · First fix to try if Q&A retrieval is weak: pair each question with its answer
- **Decided (Aarana):** if Phase 6 shows weak retrieval for questions answered in the Q&A section, the **first** experiment is exchange chunks: each analyst question chunked together with the management answer that follows it. This supersedes the "options" ordering in D14.
- **Why first:** short analyst follow-ups ("And what about margins?") and short answers ("Yes, about 24%") are meaningless alone. Pairing gives each the other's context, and it's the smallest change to the chunker.
- **How to judge it:** run it as a Phase 6 ablation on the same gold set (hit-rate@5 and MRR@10 on Q&A-sourced questions), keeping single-turn chunks as the baseline. Adopt it only if it wins.
- **Trade-off if adopted:** a chunk then has two speakers, so citations must show both (speaker becomes "analyst → management"). The D14 rule "never mix speakers" would be superseded by a new entry.
- **Revisit if:** the ablation shows no gain. Then try dropping trivial chunks (under ~20 tokens of thanks/greetings) next.

## D18 · 2026-10-15 · Extractor skip rules added from the pre-Supabase spot-check
- **Decided:** plain numbers (no currency, scale or unit) are also skipped when they're a time (`5:00`), part of a compound adjective (`360-degree`, `5-year`), after an index or list name (`Fortune 50`, `Nifty 50`), a 1–2-digit list marker followed by a capitalised sentence (`…growth. 6. Overall…`), fused to letters (`S/4HANA`), or after an apostrophe or slash (`'27`).
- **Why:** these were the wrong extractions in two rounds of 20-number spot-checks (PROGRESS.md). Measured precision went 80% → 85% → 90% on fresh samples.
- **Trade-off:** a real figure that ends a sentence with no unit and is 1–2 digits ("headcount grew by 12.") is now skipped. `5-year` durations are dropped as numbers. Both are rare in transcripts and low-value for the checker.
- **Not fixed (on purpose):** units written once for a list ("40, 50 basis points"), "11 odd percent", and labels like "stage 3". Fixing these by more regex would overfit 20-number samples. They wait for the Phase 5 evaluation on ~100 hand-labelled numbers.
- **Revisit if:** Phase 5's checker precision/recall shows these classes matter.

## D19 · 2026-10-15 · Why local showed 419 numbers and Supabase 368 (addendum to D18)
- **What happened:** the extractor changed *between* runs. Local run 1 used the first Phase 2 extractor: **419** numbers. After the first D18 skip rules, the local re-ingest gave **386**. After the second, **368**. Supabase was ingested once, after both fixes: **368**. The local DB was re-ingested each time (`truncate quantrag.documents cascade` on the local container only), so local and Supabase now match: 287 chunks, 368 numbers.
- **Rule going forward:** any extractor or parser change must be followed by re-ingesting **every** database that holds data (drop the affected documents and run `python -m ingest.run`), and the new counts go in PROGRESS.md. Idempotent ingest skips by sha256, so it will **not** pick up extractor changes on its own.
- **Revisit if:** extractor changes become frequent. Then add a stored `extractor_version` per document and re-extract numbers in place.

## D20 · 2026-10-15 · Reranker: `Xenova/ms-marco-MiniLM-L-6-v2` via fastembed, measured untuned
- **Decided:** the same cross-encoder v1 used (`cross-encoder/ms-marco-MiniLM-L-6-v2`), in its ONNX export from fastembed's supported list. It reranks the top 20 RRF results on the same "company quarter · speaker (role): text" form used for embedding (D15).
- **Options:** MiniLM-L-6 (80 MB) · MiniLM-L-12 (120 MB) · `jina-reranker-v1-tiny-en` (130 MB) · `bge-reranker-base` (1 GB, too big).
- **Why:** same model as v1 makes the v1-vs-v2 memory comparison like-for-like, and it's the smallest option.
- **Measured (smoke set, one run, untuned):** recall@5 6/10 → 9/10 with rerank; latency ~1.1 s/query; **peak RSS 1,046 MB vs 261 MB without** (load alone ≈ +100 MB; the rest appears during scoring).
- **Trade-off accepted for now:** none. At ~1 GB it wouldn't fit a 512 MB host and would push Cloud Run to 2 GiB. Tuning (PROGRESS Phase 3 a–c) needs Aarana's approval.
- **Revisit if:** batching and length caps don't bring peak RSS well under 512 MB. Then compare `jina-reranker-v1-tiny-en`, or rerank fewer candidates.

## D21 · 2026-10-15 · Smoke s05 (HUL palm oil) was a labelling miss, not an ingest or retrieval bug
- **Checked first, as asked:** the expected chunk (798, CFO prepared remarks) **is in the database**; nothing was filtered at ingest, so no re-ingest was needed. Its vector ranks 33rd of 287 for the question, because palm oil is one line in a 2,085-character turn covering several segments.
- **What retrieval returned instead:** chunks 841, 806 and 804 (dense ranks 1, 2, 7), Q&A answers by the CFO about palm-oil inflation. 804 and 841 directly answer "how did HUL respond" ("within this is to drive premiumization… Dove and Pears"; "What we are doing to counter… is to increase premiumisation").
- **Decided:** widen s05's expected quotes to include 804 and 841. The original label was too narrow: I had picked one chunk when three answer the question.
- **Caveat:** this changes a test label *after* seeing results, which can flatter scores. It's justified only because both chunks literally answer the question. Aarana should confirm it when reviewing the smoke set, and the Phase 6 gold set must be labelled before any system output is seen.

## D22 · 2026-10-15 · Keyword search uses OR semantics (any term), ordered by ts_rank_cd
- **Change:** `fts()` turns the `websearch_to_tsquery` AND query into OR (`replace(...::text, '&', '|')::tsquery`). `ts_rank_cd` still orders the results: more matched terms, closer together, ranks higher.
- **Why:** with AND, a natural-language question only matches chunks containing *every* non-stopword in it, so keyword search found 1/20 smoke questions, even ones quoting exact figures.
- **Measured (20 questions, 3 runs each, local DB):** keyword-only recall@5 **1/20 → 15/20**; hybrid (RRF) without reranker **14/20 → 19/20** (p50 ≈ 7 ms, peak RSS ≈ 284 MB); hybrid + rerank 19/20 → 18/20 (s08 drops out); vector-only unchanged (14/20).
- **Trade-off:** OR matches far more chunks (common words like "growth" match many), so keyword precision relies on `ts_rank_cd` ordering and on RRF. Slightly slower (≈0.4 → 1.8 ms).
- **Revisit if:** the Phase 6 gold set shows keyword noise hurting hybrid. Then try a minimum-match rule (at least half the terms) or `ts_rank` with length normalisation.

## D23 · 2026-10-15 · Reranker memory: batch 4, 384-token cap, rerank the top 10 (supersedes D20's top 20)
- **Target (Aarana):** peak RSS ≤ 512 MB with reranking on, recall@5 no lower than before tuning. **Measured on the 20-question smoke set, 3+ runs per setting, local DB, macOS arm64:**

| Setting (batch, max tokens, reranked) | Peak RSS, reranker on | hybrid+rerank recall@5 | p50 latency |
|---|---|---|---|
| untuned (64, 512, 20) | 1,116–1,191 MB | 18/20 (after D22) | 1.0–1.6 s |
| (a) 8, 384, 20 | 468–599 MB | 18/20 | 0.99–1.09 s |
| (a) 4, 256, 20 | 399–426 MB | 17/20 (s20 lost to truncation) | 0.62–0.65 s |
| (a) 4, 384, 20 | 374–516 MB (6 runs) | 18/20 | 0.72–0.98 s |
| **(b) 4, 384, 10** | **386–419 MB (6 runs)** | **18/20** | **0.43–0.46 s** |
| (c) smaller model | not applicable: already MiniLM-L-6, the smallest in fastembed | | |

- **Decided:** batch 4, 384 tokens, top 10. It's the only setting under 512 MB in every run with recall unchanged. Batch 4 / 384 / top 20 went over 512 MB once in 6 runs.
- **Why it works:** loading the model costs ~100 MB. The rest is inference memory, which grows with passages scored at once × their length, and ONNX Runtime keeps its peak allocation. Smaller batches and shorter inputs shrink that peak.
- **Trade-off:** the reranker sees 10 candidates instead of 20, so it relies on hybrid fusion to surface the answer. Vector + rerank drops 19 → 15/20, but hybrid + rerank, the configuration we use, stays at 18/20.
- **Honest note on "no lower than now":** before any tuning, hybrid + rerank scored 19/20 on the 20 questions. The one-question drop (s08) came from D22 (keyword OR), not from this memory tuning. Meanwhile hybrid **without** the reranker rose 14 → 19/20 at ~7 ms and ~285 MB. On this small set the reranker no longer adds recall. Phase 6 must ablate "hybrid" vs "hybrid + rerank" on the full gold set before deciding whether to keep it.
- **Caveat:** macOS RSS varies a lot between runs (one setting ranged 374–516 MB). Re-measure on Linux (Cloud Run's container) in Phase 9 before relying on the 512 MB headroom.
- **Revisit if:** Phase 6 shows the reranker doesn't earn its ~0.44 s and ~130 MB, or Cloud Run memory differs.

## D24 · 2026-10-15 · s05 label kept; completeness belongs to the gold set; chunk 798 dilution logged, not fixed
- **s05 (Aarana):** keep the label. A hit is any of chunks 798, 804 or 841 in the top 5. 841 directly answers "how did HUL respond" ("What we are doing to counter… is to increase premiumization"). The question is not reworded.
- **Completeness → Phase 6:** the full answer to s05 needs two pieces of evidence (798: price increases; 804/841: premiumisation). The gold set (`eval/gold.jsonl`) will allow **multiple evidence items per question**, and answer **completeness** (share of required evidence items present in the context / cited) is scored **separately from recall@k** (any required item retrieved). The smoke set stays "any one counts".
- **Why 798 is never retrieved:** it's a 2,085-character prepared-remarks turn by the CFO covering Hair Care, Skin Care, Personal Care, Oral Care, Foods and Nutrition. Palm oil is one sentence, so one embedding of the whole turn is diluted across six topics (vector rank 33/287 for the question).
- **Candidate fix (later, not now):** split *prepared-remarks* turns at paragraph or segment boundaries ("Turning now to Personal Care…", "Talking about Foods…"), still one speaker per chunk. **Measure it on the Phase 6 gold set, not the smoke set**, and keep it only if recall/completeness improve without hurting Q&A questions.
- **Revisit:** Phase 6, as an ablation alongside D17 (question + answer pairing).

## D25 · 2026-10-15 · Gemini model for development: `gemini-3.1-flash-lite` (production choice pending)
- **Decided for now:** `GEMINI_MODEL=gemini-3.1-flash-lite`, passed through the environment (rule 8; nothing in code). Chosen because it's the model v1 already ran on with this API key, it's not a preview, and it's the cheapest/fastest tier.
- **Available on the key (2026-10-15, `models.list`):** includes `gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-3.1-flash-lite`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.6/3.7/3.8-flash`, several `-preview` models and `*-latest` aliases.
- **Not decided:** the production model. That's Aarana's call (cost and quota) and should be compared on the Phase 6 gold set (faithfulness, correctness, latency). Avoid `*-latest` aliases and `-preview` models in production, because results must be reproducible.
- **Action for Aarana:** add `GEMINI_MODEL=` to `.env` (currently only `GEMINI_API_KEY` is there; the Phase 4 runs passed it on the command line).

## D26 · 2026-10-15 · Router: rules only, no LLM fallback yet
- **Rules:** companies by `companies.yaml` alias (word boundary, case-insensitive, longest alias first so "HDFC Bank" isn't also "HDFC"); periods from "Q1 FY27" / "FY26" / "last quarter" / "last N quarters" (resolved per company from the latest ingested quarter); `risk` > `comparison` (2+ companies or compare/vs/better wording) > `single`; `out_of_scope` when there's no company and no earnings-call vocabulary; `numeric` flag from "how much/many", %, ₹, crore, bps…
- **No LLM fallback (yet):** the brief allows one. The only case rules can't settle is "no company named but clearly a finance question" (e.g. "which IT company had the best margin?"), and that now routes to `single` with **no filter** (search everything) rather than asking an LLM. It's cheaper and explainable. Logged as a possible addition: sector words ("IT companies", "banks") → that sector's companies as a comparison.
- **Revisit if:** the Phase 6 router ablation shows misroutes that a sector rule or an LLM fallback would fix.

## D27 · 2026-10-15 · Generation: structured output, citations checked in code, tables only for comparisons
- **Structured output** (Pydantic `LLMAnswer`: `answer_markdown` with `[cN]` markers, optional `comparison_table` (metric × company cells, each with citations), `refused`, `refusal_reason`) via LangChain `with_structured_output`, temperature 0.
- **Checked in code, not trusted:** citation markers outside the provided excerpts are deleted; a table cell whose citations are all invalid becomes "not discussed"; a non-refused answer with no valid citation is withheld as a refusal; tables are dropped unless the route is `comparison` (the model added tables to single-company answers in the first Phase 4 run).
- **Refusals** always list what *is* available for the companies asked about (or for all companies when out of scope). A score floor (`REFUSAL_MIN_RERANK`) exists but stays **unset until Phase 6 tunes it**; until then only "no hits" and the model's own judgement refuse.
- **Not streaming yet:** Phase 4 generates the whole answer. Token streaming over SSE is Phase 7's job (the API). Whether structured output can stream partial `answer_markdown`, or the answer text should be streamed and the table produced separately, is decided there.
- **Known failure (kept for the Phase 6 report):** "Compare TCS and Infosys on large deal wins" labels TCS's *total* TCV ($9.5 billion) as "Large Deal TCV". The cited chunk has the number; the label is wrong. Citation checks can't catch this; the faithfulness judge should. It also wrote "$2.4 billion" where the source says "$2.4 bn" (same value; the prompt asks for exact copies).

## D28 · 2026-10-15 · CI, secrets hook, and a separate test database
- **CI** (`.github/workflows/ci.yml`, on push/PR to `v2` and `main`): Python 3.11 · `pip install -e backend[dev]` (pip cache keyed on `backend/pyproject.toml`) · ruff · pytest over `backend/tests` + `scripts` with coverage of `ingest`, `numcheck`, `retrieve`, `generate`, `check_manifest` · a `pgvector/pgvector:pg17` service container so the DB tests run · fastembed models cached under `FASTEMBED_CACHE_PATH` (keyed on `retrieve/search.py`). Test counts and coverage are reported in [GitHub Actions](https://github.com/aaranarc/earnings-call-analyst/actions/workflows/ci.yml?query=branch%3Amain).
- **Model test added** (`test_models.py`): the cache only matters if a test loads the models, so CI now loads the real ONNX models and checks embedding size = `vector(384)` in the schema and that the reranker ranks a relevant passage above an unrelated one.
- **Ruff isort `known-first-party`** lists our modules explicitly, so import order is the same whether ruff runs from the repo root (CI) or `backend/`.
- **Pre-push hook** (`.githooks/pre-push`, enabled with `git config core.hooksPath .githooks`): runs `gitleaks git` on only the commits being pushed (`remote..local`, or `--not --remotes` for a new branch) and blocks on any finding. **Fails closed** if gitleaks isn't installed. Verified: the full history (67 commits) is clean; a throwaway repo push with a generated fake GitHub token was blocked and a clean push went through.
- **Incident and fix: tests wiped the local dev data.** Running the DB tests locally with `TEST_DATABASE_URL` pointing at the dev database (`qr-pg`/`postgres`) dropped the `quantrag` schema, as designed. Re-ingested (4 docs, 287 chunks, 368 numbers, identical). **Tests now use a separate database** (`quantrag_test` in the same container). The localhost guard protected Supabase, but not local dev data.
- **Two artifacts were committed by mistake** (`backend/.coverage`, `backend/quantrag.egg-info/`). Removed from the index during the alpha freeze; `.gitignore` covers subsequent generated files.

## D29 · 2026-10-15 · Pin `GEMINI_MODEL=gemini-3.1-flash-lite` in `.env.example` (supersedes D25's "pending")
- **Checked** ai.google.dev/gemini-api/docs/models on 2026-10-15. Stable (non-preview) flash-family text models: `gemini-3.8-flash`, `gemini-3.6-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-flash-lite`. `gemini-3-flash-preview` is preview; `gemini-3.1-flash-lite-preview` is shut down; 2.5 models are unlabelled and limited to past users.
- **Pinned** `gemini-3.1-flash-lite`: stable, the model all Phase 4 results were measured with, and the cheapest tier. Aarana puts it in `.env`.
- **Final choice on the Phase 6 gold set:** compare it with `gemini-3.5-flash-lite` and `gemini-3.8-flash` on correctness, faithfulness, refusal accuracy, latency and cost.

## D30 · 2026-10-15 · Router report: 85% fully correct; filters help, never hurt
- **Router accuracy** (`eval/router_report.py`, 20 new hand-labelled queries in `eval/router_queries.jsonl`, separate from unit tests, labelled with the *ideal* route): companies **18/20 (90%)**, periods **19/20 (95%)**, intent **18/20 (90%)**, all three **17/20 (85%)**. Misses: r08 "Which bank had the best CASA ratio?" and r17 "How is the IT services sector doing on pricing?" (no sector rule and "best" isn't comparison wording → `single`, all transcripts); r11 "…this quarter" (not parsed as the latest quarter). All three are known gaps from D26, labelled in on purpose.
- **Smoke recall@5, router off → on** (20 questions, one run each, since recall is deterministic): vector 14 → 14 · keyword 15 → **18** · hybrid 19 → 19 · vector+rerank 15 → **17** · keyword+rerank 17 → **18** · hybrid+rerank 18 → **19** (s08 recovered). Company filters mostly help keyword search, which with OR semantics matches many off-company chunks.
- **Scaling caveat found:** vector ranks were identical with and without filters. pgvector's HNSW index finds nearest neighbours first (`ef_search` = 40 by default) and filters afterwards, so a filtered query can return fewer than k rows once the corpus is large. Harmless at 287 chunks. Before the 96-transcript corpus, set `hnsw.iterative_scan = relaxed_order` (pgvector ≥ 0.8; Supabase has 0.8.2) and re-measure.
- **Candidate router fixes (not built; propose for Phase 6):** sector words ("banks", "IT services", "FMCG") → that sector's companies as a comparison; "best/strongest/highest/lowest" → comparison; "this quarter"/"latest quarter" → latest ingested period.

## D31 · 2026-10-15 · Number checker design: sentence-level citations, stated precision, conservative "derived"
- **Lookup order** per number in an answer: (1) the chunks cited **in the same sentence** (a sentence with no marker uses all the answer's citations) → `verified`; (2) other chunks of the same transcript(s) → `found_elsewhere`; (3) arithmetic on two numbers from **one** cited chunk → `derived` with a formula; (4) otherwise `unverified`. Comparison-table cells are checked against each cell's own citations.
- **"Same number"** = equal after rounding to the precision the answer states (brief's rule: "25%" verifies a source "25.3%"; "25.35%" does not), on the canonical scale ("$2.4 billion" = "$2.4 bn" = "$2,400 million"), with a matching unit. Two loosenings for known extraction gaps: a stored number with **no unit** matches on value alone (D18: "40, 50 basis points"), and a **dropped direction word** still matches ("130 bps" vs "down 130 bps").
- **"derived" only within one chunk** (difference, % change, share, pp, % → bps). Why: with ~50 numbers in the cited chunks there are ~2,500 pairs, so cross-chunk arithmetic would often "explain" a wrong number by coincidence. A made-up number marked `derived` is hidden from the user; a real calculation marked `unverified` is only a false alarm. When unsure, the checker says `unverified`.
- **Extractor changes alongside:** `decimals` (stated precision) on each number, and a `pp` unit ("percentage points", "pp") so "1.3 percentage points" isn't read as "1.3 percent". Re-extracting every stored chunk gives **0 changed rows**, so no re-ingest was needed (checked, per D19).
- **Bug fixed in passing:** the "don't end a sentence after Mr./Ms./Rs." rule in `ingest/parse.py` (and the new checker) looked at the wrong position and never applied. Fixed; re-chunking all 4 transcripts gives **identical chunks**, so no re-ingest.
- **Revisit if:** the labelled evaluation shows real calculations across two chunks (e.g. A&P ÷ turnover) being flagged often enough to annoy users. Then allow cross-chunk `derived` only for pairs from the same document and period.

## D32 · 2026-10-15 · Checker evaluation: 77 real numbers + 35 deliberately corrupted copies, labelled blind
- **Problem:** across 37 real answers (`gemini-3.1-flash-lite`, temperature 0), the checker found 77 numbers: 76 `verified`, 1 `derived`, **0 `unverified`**. If that holds under human labels, there are no positives for the brief's headline metric (precision and recall of `unverified`), and the evaluation couldn't show the checker catching a wrong number.
- **Decided (needs Aarana's OK; departs from the brief's "numbers taken from real answers"):** add 35 **corrupted copies** of real answer sentences, each with one number changed by a fixed, seeded rule: a changed digit, a wrong scale word (crore → lakh, billion → million), % ↔ bps, or a ×10 decimal slip. Real and corrupted rows are **shuffled under neutral ids** (`q001…`) so the labeller can't tell them apart. The mapping and the checker's statuses live only in `eval/results/numcheck_answers.json`.
- **Reporting:** `eval/numbers_eval.py` reports accuracy, the confusion matrix and `unverified` precision/recall **separately for real, corrupted and all rows**. Corrupted rows measure whether the checker *can* catch errors. They say nothing about how often the generator makes them.
- **Checker's own verdicts on the corrupted rows (preview, not gold):** 24 unverified, 5 found_elsewhere, 4 verified, 2 derived. Human labels decide whether e.g. a corrupted "25%" really does appear in the cited excerpt (then `verified` is correct) or the `derived` ones are coincidences (the D31 risk).
- **Revisit if:** a stronger or newer generator model produces natural errors. Then rebuild the sheet from real answers only, as the brief intended.

## D33 · 2026-10-15 · Answer keys and corruption maps live in git-ignored `eval/private/` until labelling is done
- **Rule (Aarana):** any file that reveals what a labeller should conclude (answer keys, corruption maps, the checker's verdicts on rows being labelled) goes in `eval/private/` (git-ignored) until labelling is complete. Scripts that would write key-derived files into tracked folders must write to `eval/private/` instead while labelling is incomplete. `eval/numbers_eval.py` writes partial scores only to `eval/private/numcheck_partial.json`, and writes `eval/numbers_gold.jsonl` + `eval/results/` only once every row is labelled.
- **Why:** the first sheet's key (`eval/results/numcheck_answers.json`, commit `efa92f7`) was pushed to GitHub, which breaks blinding for anyone who opens it.
- **What was done about the leak:** the file is deleted from the tree (history keeps it; no force push). The sheet was **rebuilt with a new seed (7 → 11) and new ids (`n001…`)**, so the leaked map doesn't describe the new sheet. It still shows the checker's verdicts on the 77 real numbers (all verified/derived), which could hint that a row is real. Aarana must not open it before labelling.
- **The labelling page** (`eval/label_server.py`) reads only the sheet, never the key, and binds 127.0.0.1 only.

## D34 · 2026-10-15 · Context-swap corruptions, a 3-way label, and recall per corruption type (extends D32)
- **Added (Aarana):** ~10 **context swaps**, where the number is unchanged and present in the cited excerpt but the sentence attributes it to the wrong **company** (same sector), **quarter** or **metric**. Like the known TCV mislabel (D27). The final sheet has **120 rows**: 77 real · 33 value corruptions (digit 14, decimal 12, unit 5, scale 2; 2 of 35 dropped because the corrupted text no longer parsed as a number) · 10 context swaps (company 4, metric 4, period 2).
- **Label scheme (Aarana):** **supported / not supported / unsure** (replacing the 4-way status labels in D32). "Supported" means the cited excerpts support the number *as the sentence uses it*: value, unit, scale **and** company, quarter, metric. `unsure` rows are excluded from scores and counted.
- **Scoring:** positive = not supported. Two flag definitions: **red** (`unverified`) and **any non-green** (`unverified`, `found_elsewhere` or `derived`). Precision and recall for each, for real / corrupted / all, plus **recall per corruption type**.
- **Known limitation, expected:** the checker matches **values**, not what they describe. All 10 context swaps came out `verified` (checker's own verdicts), so their recall should be ~0 under either flag definition. Catching wrong attribution needs claim-level checking (does the excerpt say *this company's* *metric* in *this quarter* is X?). That's the Phase 6 faithfulness judge's job, not value matching.
- **Revisit if:** context-swap errors turn out common in real answers (the gold set and judge will show). Then add a cheap attribution check: the company and period in the sentence must match the cited chunk's metadata.

## D35 · 2026-10-15 · Phase 6 retrieval tooling before human gold data
- Build a validator and retrieval runner independently of the deferred Phase 5 labels. Never manufacture gold labels or report benchmark results without human review.
- Measure hit@5, MRR@10, and evidence completeness separately (D24). Exclude unanswerable questions from evidence denominators.
- Use a global ranking for retrieval ablations, including comparison questions; production retains per-company retrieval. This allows meaningful rank cutoffs, but does not measure the production comparison context.
- Read-only corpus validation precedes model loading. Reports retain gold/corpus hashes and settings and refuse overwrites. See `docs/EVALUATION.md` for commands and remaining Phase 6 work.

## D36 · 2026-10-15 · Dashboard-first thesis workspace
- Owner chose an evidence-backed thesis dashboard and supplied dark magenta/violet tokens with Geist fonts. Telegram is deferred.
- Add a Next.js frontend and a local FastAPI adapter for the existing RAG engine. Keep credentials on the server; API database transactions are read-only.
- Stream progress followed by the fully validated answer rather than exposing unchecked generation tokens. Health checks stay lightweight; model warm-up happens on the first question.
- User assessments remain manual and unresolved by default. Label demonstration scenarios explicitly; never fabricate cross-quarter evidence for the current single-quarter corpus.
- Preserve browser-local notes and source references. Editing evidence resets assessment and review. Authentication, automatic matching, cross-device persistence and production deployment remain future work.
- Coverage is the dated ingest snapshot. Public gold metrics stay empty until a completed, reviewed report is published.

## D37 · 2026-10-15 · Append-only evidence and honest coverage gates
- Replace the editable two-slot interface with evidence timeline entries. Store period, capture date (unknown for legacy notes), kind and source-bearing text. Adding an entry resets assessment/review; historic evidence is retained.
- Workspace v2 validates imports and migrates v1 while preserving its storage key as a recovery copy. Import merges identical rows, retains conflicting rows as distinct copies, rejects malformed data before writing. Export/import operate on real research; illustrative examples cannot be exported as personal data.
- Number badges describe a value match, not a verified claim. Citation drawers expose section metadata and adjacent stored chunks from the same document; neighbors are context, not necessarily generation inputs.
- Refuse before retrieval when a named company's requested fiscal periods are missing. Comparisons using multiple periods display a warning rather than implying same-quarter comparability.
- Official TCS Q2–Q4 FY26 and Infosys Q2 FY26 sources were located, but direct PDF downloads returned HTTP 403. Recorded candidates separately in `data/source_candidates.json`; no fabricated PDFs, manifest completion, hashes or corpus expansion.

## D38 · 2026-10-15 · Source-quoted suggestions and a bounded portfolio release
- On-demand thesis checks evaluate only selected ingested periods, validate every quoted span against its cited chunk, and propose support/challenge/insufficient. Missing coverage or invalid quotations never produce a supported assessment. The user reviews and saves evidence; adding it resets their assessment.
- A generation evaluator uses explicit non-Gemini judge configuration, a fixed claim-level rubric, input hashes and frozen corpus provenance. Human agreement and the planned reviewed gold are required before deliberate public-report publication; numeric value matches are not semantic numeric precision.
- Production POST endpoints require a server-only shared token. A Next route handler passes it from server environment, bounds bodies, limits routes/methods and rejects explicit cross-origin submissions. Anonymous portfolio use is bounded by a transactional daily request budget; this is not account authentication or a dollar billing cap.
- Images run as non-root; retrieval models ship in the API image. Single API worker bounds model memory. SQLite budgets persist only with a persistent volume; free ephemeral hosting resets them on replacement.
- Owner deferred the hosting choice until release checks after discussing Render idle sleep. No paid service or public deployment is authorized by that deferral.

## D39 · Free public portfolio deployment
- Owner explicitly chose free hosting and confirmed Render workspace “aarana's supabase”, superseding D38's hosting deferral. Use Vercel Hobby for the Next frontend and Render Free for the Docker API.
- Accept Render idle sleep. Serve committed coverage/eval snapshots in Next without waiting for the API; warm health silently and show progress/retry for live queries.
- Keep the same server-only token in Vercel and Render; frontend PUBLIC_ORIGIN is the canonical https://quantrag.vercel.app. No paid service was provisioned.
- Vercel source-files deployment avoids requiring an unconfigured GitHub integration. Auto-deploy is not claimed; future code releases need an explicit deployment until integration is connected.

## D40 · 2026-10-16 · Conservative sector routing and relative periods
- Expand rule-based routing for bank/banking, IT-services/company and FMCG/consumer questions only when no known company is explicitly named. Select all configured peers; retain strict coverage refusal before retrieval when any peer lacks the requested transcript. This prevents incomplete coverage from being presented as a sector-wide ranking.
- Interpret this/latest/most-recent quarter as latest ingested per company, never the current calendar quarter. Explicit fiscal periods take precedence over relative language. Preserve the existing union-of-periods semantics: a comparison with different company latest quarters can still conservatively refuse for incomplete common coverage.
- Keep original development results immutable. Fixes were informed by the development queries, so passing those queries is regression evidence rather than a held-out benchmark.

## D41 · 2026-10-16 · Verified owner-supplied corpus expansion
- Accept the four owner-downloaded official PDFs after checking their identities and fiscal periods. Preserve original downloads, register exact file hashes, and retain ignored raw PDFs locally. Do not infer missing documents or change the frozen corpus window.
- Direct local PostgreSQL connectivity timed out while the authenticated Supabase connector remained healthy. Reuse the production parser/chunker, embedding model and number extractor locally, then send one atomic idempotent SQL statement per document through that connector. No schema or access-policy changes were needed. Verify counts, vector dimensions, source/hash parity, preservation of original documents and zero changes on rerun.
- Coverage is 8/96 (latest-four gate 7/48), not a completed corpus. Old development measurements remain historical until fresh reviewed evaluation; do not promote them to gold metrics after adding documents.
