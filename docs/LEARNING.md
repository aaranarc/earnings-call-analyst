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

## Phase 1: Corpus tooling (2026-10-15)
- **v1's corpus was much smaller than it looked:** 9 PDFs, but only 6 were real transcripts and only 1 made it into the shipped index. So v2's numbers can't honestly be presented as "improved from v1" on quality. There was no real v1 quality to compare against. The fair v1 → v2 comparison is memory (the reranker story).
- A **manifest** (`data/manifest.csv`) is a written list of exactly which files make up the dataset: where each came from, which quarter it covers, and a fingerprint of its bytes. The dataset becomes reproducible, and anyone can check they have the same files.
- The fingerprint is a **SHA-256 hash**: change one byte of the PDF and the hash changes completely. A tool computes it (`--fill-sha`) so nobody types it by hand. Later, ingestion uses it to skip PDFs already in the database (idempotency).
- **Indian fiscal years run April to March:** Q1 FY26 is April–June 2025. Companies write labels inconsistently, so we store our own normalised label *and* the calendar quarter-end date, and code checks that the two agree. Rule: trust the date, not the label on the cover.
- I chose a **fixed window** (the same 8 quarters for every company) so a question like "compare TCS and Infosys last quarter" always has both sides available.
- The checker treats an unfilled row as **pending, not an error**, so the corpus can be filled gradually and the tool still tells you exactly what's left.
- **Aliases** (TCS = Tata Consultancy Services) live in one YAML file that both the checker and the router (Phase 4) read. The checker refuses an alias shared by two companies, because an ambiguous alias would route a question to the wrong company.
- **Why ≥90 of 96 and not all 96:** some transcripts genuinely don't exist or can't be fetched legitimately. Without a cap, one missing PDF blocks the project. Without the excuse rule, "90 rows" could hide the fact that one company is missing its recent quarters. So each gap needs a written reason, and the most recent 4 quarters (Tier A) allow no gaps.
- **Gates instead of one finish line:** the checker reports three gates (`phase2` → `A` → `B`). Later work can start as soon as it has enough data (ingestion needs just one transcript per sector to test on) rather than waiting for all 96 downloads.

## Phase 2: Ingestion (2026-10-15)
- **Ingestion turns PDFs into searchable rows:** text per page → who is speaking → cut into chunks → each chunk turned into a vector (a list of 384 numbers that captures its meaning) → stored in Postgres next to the raw text.
- **Speaker turns matter** because "management said X" and "an analyst asked about X" mean different things. Analysts are identified because the moderator introduces each one ("next question is from the line of X from Y"). Management is identified because they're on the cover or speak before Q&A.
- **A chunk never mixes two speakers,** so every citation points at one person. The cost: Q&A turns are short, so chunks average 105–175 tokens rather than the 350–500 the brief suggested. To give short turns context, the vector is computed from "company, quarter, speaker, role" + text, while the stored text stays exactly as spoken.
- **Token limits are real:** the embedding model only reads the first 512 tokens. So chunk size is counted with the model's own tokenizer, and chunks are capped at 450 tokens.
- **Idempotent** means running it twice has the same effect as once. Each PDF's SHA-256 fingerprint is stored. If it's already there, the PDF is skipped. Each PDF is written in one transaction (all or nothing), so a crash never leaves half a transcript.
- **PDFs aren't clean text:** one TCS font made the extractor print "O(cid:431)icer" for "Officer". Fixes: a second extractor for broken pages, Unicode normalisation for ligatures (ﬁ → fi), and a one-character mapping that I checked against every occurrence before trusting it.
- **Numbers are pre-extracted at ingest** with the same code that will later check numbers in answers, so "₹72,275 crore" in a transcript and "₹72,275 cr" in an answer normalise to the same value (7.2275 × 10¹¹ INR).
- **The DB test refuses to run on anything but localhost,** because it wipes the schema. A test should never be able to damage production data.
- **Spot-checking before loading production data:** I printed random chunks and numbers and marked each right or wrong by hand. It caught things tests didn't, like "360-degree" and "5:00 PM" being stored as figures. Measured precision rose from 80% to 90% over three fresh samples.
- **Stop before overfitting:** after each fix I drew a *new* random sample rather than re-checking the same one, and I stopped adding regex rules after three rounds. Rules tuned to one small sample can look perfect and still fail on the next transcript. The bigger hand-labelled set in Phase 5 is the real test.

## Phase 3: Retrieval (2026-10-15)
- **Two ways to find passages:** vector search finds text with similar *meaning* (good for paraphrases). Keyword search finds the *exact words* (good for names, tickers, "ECLGS"). Hybrid runs both.
- **RRF (reciprocal rank fusion)** merges two ranked lists using only ranks: each chunk scores 1/(60 + rank) per list, summed. The two searches score on different scales (cosine similarity vs keyword rank), so ranks are the fair common currency.
- **`ts_rank_cd` is not BM25.** BM25 weights rare words more (IDF) and stops rewarding a word repeated many times (saturation). `ts_rank_cd` mostly rewards query words appearing close together. That's fine here because RRF only uses the keyword list's *order*, and keeping keyword search in Postgres means one database, one filter, and nothing extra in memory.
- **A reranker (cross-encoder)** reads the question and each candidate *together* and scores how well the passage answers it. More accurate than comparing two separate vectors, but much slower, so it only reorders the top 20.
- **Measure before tuning:** a 10-question smoke test showed the reranker lifts recall@5 from 6/10 to 9/10, but costs ~1 GB of peak memory and ~1 s per question. It also showed the keyword search as specified finds almost nothing, because it requires every word of a full question to match. Both were found by measuring, not assuming.
- **ONNX isn't automatically lighter:** it removes PyTorch, but inference memory depends on how many passages are scored at once and how long they are. Loading the model was +100 MB; scoring pushed the peak to ~1 GB.
- **AND vs OR in keyword search:** requiring every word of "What effective tax rate does Infosys expect for FY25?" to appear in one chunk almost never succeeds. Matching *any* word and ranking by how many matched lifted keyword-only recall from 1/20 to 15/20. Combined with vector search, recall went from 14 to 19 of 20.
- **Where reranker memory goes:** loading the model costs ~100 MB. Running it on 20 passages × 512 tokens in one batch is what spiked memory to ~1.1 GB. Scoring 4 at a time, capping inputs at 384 tokens and reranking only the top 10 brought the peak to ~390–420 MB with the same recall and half the latency.
- **Run it three times:** the same memory setting measured 374 MB in one run and 516 MB in another. One run would have given either a false pass or a false fail against the 512 MB target.
- **A fix can make another part redundant:** once keyword search worked, plain hybrid search (no reranker) scored as well as the reranked version on this set. Keep measuring the whole pipeline, not just the part you changed.

## Phase 4: Router and generation (2026-10-15)
- **The router is plain rules, not an LLM:** it looks for company names and aliases ("Tata Consultancy" → TCS), quarters ("Q1 FY27", "last two quarters") and words like "compare" or "risk". Rules are free, instant, and you can explain exactly why a question went where it did.
- **Filters come from the router:** once it knows the question is about TCS in Q1 FY27, retrieval only searches those chunks. That's why routing matters even with good search.
- **The model gets numbered excerpts [c1]…[cN]** and must tag every factual sentence with the excerpt it came from. Then *code* checks every tag points at a real excerpt and removes any that don't. An answer with no valid tags isn't shown at all.
- **Structured output** means the model returns a fixed shape (answer text, optional table, refused yes/no, reason) instead of free text, so the code can rely on it.
- **Refusing is a feature:** if nothing relevant is found, or the model says the excerpts don't answer it, the system says so and lists which quarters it *does* have for that company. Questions about a quarter that isn't ingested are refused before any LLM call, which costs nothing.
- **Citation checks aren't truth checks:** one answer cited the right chunk but called TCS's total contract value "large deal" value. Checking that claims *match* their sources is what the Phase 5 number checker and the Phase 6 faithfulness judge are for.

## Pre-Phase 5: CI and safety nets (2026-10-15)
- **CI (continuous integration)** re-runs lint and every test on GitHub's machines on each push, with a real Postgres in a throwaway container. "It works on my laptop" isn't enough. The badge in the README shows whether the latest push passed.
- **Coverage (75%)** is the share of code lines the tests actually execute. It shows what's untested (CLIs, the spot-check tool), not whether the tests are good.
- **A pre-push hook** is a script git runs before every push. Ours runs gitleaks, a scanner for API keys and passwords, on just the new commits and refuses the push if it finds one. It "fails closed": no scanner means no push.
- **Separate test and dev databases:** my own DB test wiped my local data because both used the same database. The guard stopped it touching Supabase, but not my laptop. Now tests get their own database.
- **Measuring the router:** a labelled set of 20 questions (with the ideal answer for each) shows it gets 85% fully right, and exactly where it fails: sector questions like "which bank…" and "this quarter". Turning it on improved the reranked search from 18 to 19 of 20.
