# Phase 6 retrieval evaluation

The runner is ready for a human-reviewed gold set. No gold questions or benchmark scores have been generated.
The number-checker labels remain a separate Phase 5 task. Generation and publication tools are implemented below. Reviewed generation/judge runs,
human calibration, model comparison, refusal threshold selection and the observed failure-case report remain pending.

## Prepare gold data before running the system

Write `eval/gold.jsonl` with one JSON object per question. Each row needs:

- `id`: unique nonempty string.
- `question`: unique question; whitespace/case variants count as duplicates.
- `human_verified`: `true` only after a person checks the source transcript.
- `reviewed_by`: the reviewer's name or identifier.
- `answerable`: boolean, based on the frozen corpus.
- `evidence`: required evidence items, each with `symbol`, `fiscal_label`, and `quotes`.

Each evidence item describes a separate fact needed for a complete answer. Its nonempty `quotes` list contains
alternative exact substrings that support that fact. Matching requires the same company and quarter.
Unanswerable questions have an empty evidence list. Do not copy the tuned smoke set into the held-out gold set.
The roadmap calls for 60 human-verified questions; this tool permits smaller sets for development and records
its denominator. A small run is not the completed Phase 6 benchmark. Review flags are declarations, not proof
that a human actually performed the review.

```bash
# Offline validation: no database connection, model download, or generation call.
.venv/bin/python eval/retrieval_eval.py --gold eval/gold.jsonl --validate-only

# Supply SUPABASE_DB_URL through your environment, as for the existing evaluation scripts.
# Each output path must be new. Add --rerank to include reranker ablations.
.venv/bin/python eval/retrieval_eval.py --gold eval/gold.jsonl \
  --rerank --out eval/results/retrieval_gold_run01.json
```

Before loading models, the runner verifies every evidence item exists in the selected database. It uses a
read-only, repeatable-read transaction. A failed schema/corpus check produces no report. Reports record the gold
file hash, Git revision and dirty flag, transcript hashes, model identifiers, retrieval settings, per-question
chunk IDs, evidence ranks, and timings. Existing reports cannot be overwritten. Keep the labelled gold file
unchanged during a run and preserve it with the report. The runner rejects a file changed during execution.

## Metrics and ablations

The runner evaluates dense, keyword, and hybrid retrieval, each with routing off/on and optionally reranking
off/on. Routing applies predicted company/period filters and skips retrieval for out-of-scope questions. Gold
metadata is used only for checking results, never as a retrieval filter.

- **hit_at_5**: fraction of answerable questions with at least one evidence item in the first five hits.
- **mrr_at_10**: mean reciprocal rank of the first matching hit in the first ten; a miss contributes zero.
- **completeness_at_5**: mean fraction of required evidence items covered by the first five hits, per question.
- **p50_s**: median route + retrieval time across all questions, excluding model startup and corpus validation.

Unanswerable questions are excluded from the three evidence-metric denominators; these metrics are `null` if
there are no answerable questions. Retrieving no chunks does not establish correct refusal: the generation
and refusal evaluation uses the separate generation runner described below.

For comparisons, this runner uses a single global ranking across the routed companies. Production answers still
retrieve separately per company to prevent crowding. These results measure global retrieval, not production
comparison-context completeness. Per-question hit IDs make this distinction auditable. Timings are sequential
single-run diagnostics affected by cache warm-up; they are not controlled latency benchmarks.

## Generation, refusal and cross-family judging

`eval/generation_eval.py` uses the same reviewed gold schema and validates source evidence before loading
models or calling providers. It runs the production answer/refusal path, then asks an explicitly configured
**non-Gemini model family** to judge correctness and claim faithfulness. The judge checks attribution, period,
metric, units, scale, direction and comparison basis. Judge output is model opinion until human-calibrated.
The API endpoint must support the OpenAI chat-completions JSON format; configure `JUDGE_API_URL` (full HTTPS
chat-completions endpoint), `JUDGE_API_KEY`, `JUDGE_MODEL`, `JUDGE_FAMILY`. No judge model is guessed.

```bash
.venv/bin/python eval/generation_eval.py --gold eval/gold.jsonl --out eval/runs/generation-01.json
```

Run once per generator model/configuration using new output paths. Reports preserve generator/judge IDs,
rubric hash, frozen gold/corpus provenance, per-question answers/citations, refusal decisions and timings.
`number_value_match_rate` is a diagnostic only; it is **not** semantic numeric precision.
Model comparison and refusal-threshold ablations require actual runs on the reviewed dataset; the tools
cannot establish a best model or threshold without those measurements.

## Human agreement and deliberate publication

Review every non-refused answer independently in a CSV with `id,faithful,reviewed_by`.
Labels are `supported`, `not_supported`, or `unsure`. Review the claim against its cited passages before
looking at the model judge's verdict. `unsure` is excluded and counted. Cohen's kappa is undefined (`null`)
when there is no marginal variation; raw agreement is retained.

```bash
.venv/bin/python eval/publish_eval.py --generation eval/runs/generation-01.json \
  --retrieval eval/results/retrieval_gold_run01.json --human-labels eval/generation_human.csv \
  --out eval/results/public_eval.json
```

Publication requires matching frozen gold/corpus, at least the planned 60 reviewed questions, an explicitly
declared cross-family judge, and complete human review of answered outputs. It never manufactures five
failures: if fewer occur, only the observed failures are included. Numeric precision still requires the
separate deferred Phase 5 human labels. No model, corpus or latency benchmark is claimed by passing unit tests.
