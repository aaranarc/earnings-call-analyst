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
