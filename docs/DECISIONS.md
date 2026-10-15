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
