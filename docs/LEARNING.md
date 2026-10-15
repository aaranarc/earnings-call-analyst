# Learning log

Plain-English notes on what was built and why, one section per phase. Written so every part can be explained in an interview.

## Phase 0: Audit and baselines (2026-10-15)
- Before rebuilding anything, I froze v1 with a git tag (`v1-final`). A tag is a permanent name for one commit, so "before vs after" comparisons always point at the same code.
- I searched every stored file version in git history for API keys. A key committed once stays in history even after you delete the file, so a leak means rotating the key, not just removing the file.
- **RSS** (resident set size) is the RAM a process actually holds. **Peak** RSS matters more than average, because the server is killed the moment usage crosses its memory limit (that's the OOM, "out of memory", crash).
- Loading v1's cross-encoder reranker through PyTorch pushed peak RSS from about 172 MB to 512–692 MB across five runs, at or above Render free's 512 MB limit every time. That's why v1 disabled it. v2 brings it back using ONNX (fastembed), which avoids loading PyTorch.
- **p50/p95 latency:** p50 is the typical request time; p95 is the slow tail that 1 in 20 users feels. Report both, because averages hide the tail.
- The audit found that three of v1's "transcripts" were one-line placeholder PDFs, and v1's eval answers had been written to match them. An eval is only as honest as its data. That's why v2 requires every gold question to be verified by a human against the real PDF.
- v1's router matched company names as plain substrings ("HDFC" in the question). v2 uses an alias list per company, so "Tata Consultancy" and "TCS" resolve to the same company.
- One memory reading is not a measurement: my first reranker run said 512 MB, and repeats said up to 692 MB. Now the script appends every run and I report the range.
- I ran the baseline on an extracted copy of the tagged code, because simply opening the old vector database with a newer library version rewrote its files. Measuring something shouldn't change it.
