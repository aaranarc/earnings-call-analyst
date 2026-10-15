# QuantRAG dashboard

Next.js/React frontend with Geist and Geist Mono, using the owner's charcoal dashboard and visual-report references.

From the repository root, run the API in one terminal:

```bash
.venv/bin/pip install -e 'backend[dev,api]'
.venv/bin/python -m uvicorn quantrag.api:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000
```

Then run the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:3000/watchlist. Node 22+ is recommended. The frontend proxies `/api/*` to the loopback API;
`API_ORIGIN` can override that server-side destination. Database/model credentials stay in Python; the optional
shared API token is configured in both servers and stays server-only.

## What works

- `/`: question entry, four route examples, API-backed coverage and published evaluation cards.
- `/watchlist`: labelled illustrative workspace plus separate local research; create, filter, export, edit evidence,
  assess and review theses. Editing evidence resets the assessment. Storage errors are surfaced.
- `/ask`: live existing RAG engine, citation drawer/bottom sheet, matched-number highlighting, status tooltips,
  comparison table, retrieval scores, timing trace, local answer pins, and saving cited answers to theses.
- `/eval`: reads the designated public report; absent reports show an honest pending state with no fake KPIs.
- `/how-it-works`: accessible SVG pipeline and limitations.

## Boundaries

Thesis checks suggest source-quoted evidence on demand; final assessment remains **manual**. Example quotes are illustrative and never
saved as real research. LocalStorage is browser-local, without accounts or sync. Coverage is explicitly labelled
with the committed ingest snapshot date; refresh `eval/results/ingest_stats.json` when ingest changes.

The API streams status and then one fully checked answer. It does not stream unchecked model tokens. The health
call checks configuration without loading the large models; the first question performs model warm-up. A single
in-flight request is allowed per process; additional requests return 429. This is a local portfolio implementation,
with production access controls prepared. Production requires a shared server-only API token and uses an atomic SQLite daily request budget. Run one API instance with a persistent usage volume for a restart-persistent cap; distributed scaling needs a shared quota store.

Public evaluation schema at `eval/results/public_eval.json`:
`status`, `metrics[{name,value,definition}]`, `ablations[{name,hit_at_5,mrr_at_10}]`,
`agreement{ kappa, sample_size } | null`, `failure_cases[{question,finding}]`, and
`last_run{date,commit} | null`. Publish only actual completed evaluation results. The file is not populated yet.

## Verification

```bash
npm run build
npm run typecheck
npm run test:e2e
```

Local browser tests use installed Chrome. CI installs Playwright Chromium. Tests cover persistent research,
evidence transfers, citations, rate-limit messaging, pending evaluations, 375px layouts and automated WCAG AA
checks. Automated accessibility checks supplement, rather than replace, keyboard and visual review.

## Visual research workspace

The current palette follows the later charcoal dashboard references, superseding the initial magenta-glow spec.
The coverage matrix comes from `/companies`; gaps are missing transcripts, not zero financial values.
The assessment donut counts local manual thesis statuses (or clearly labelled examples); its legend filters the list.
Research brief opens the complete workspace, independent of list filters, and supports browser Print / Save PDF.
It preserves evidence notes and source references. It is not an automatically generated investment recommendation.

## Workspace recovery and source context

Personal research now uses `quantrag.theses.v2`. On first load, v1's earlier/later notes become timeline entries;
no capture dates are invented, and the original v1 key is retained. New entries append, never replace prior notes.
Import accepts version 1 or 2 JSON exports (up to 5 MB, 500 theses, 1,000 entries per thesis), previews the count,
and merges without overwriting existing research. Conflicting IDs become imported copies; identical rows are skipped.
Examples cannot be exported/imported as personal research. Browser storage can still be lost; keep JSON backups.
Citation drawers display adjacent stored excerpts for context, separate from the exact cited chunk.
A “Value matched” badge verifies numeric matching only, not the truth or attribution of the surrounding claim.

## On-demand thesis checks

Open a personal thesis → Check against earnings calls → select available periods → Check selected calls.
The model suggests support/challenge/insufficient with exact transcript quotations, which the server validates.
Keep quoted evidence appends to the timeline and resets the assessment to unresolved. Suggestions never
silently mark a thesis supported. One call cannot establish a cross-quarter trend; the UI says so.
Deployment options, budget limits and setup: [`docs/DEPLOYMENT.md`](../docs/DEPLOYMENT.md).
