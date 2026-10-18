# Scheduled operations

The [operations workflow](https://github.com/aaranarc/earnings-call-analyst/actions/workflows/operations.yml)
runs public readiness checks daily at 02:30 UTC (08:00 India time). It checks the dashboard, covered documents,
evaluation response and configured API, without generating an answer or consuming model quota. It makes one
API readiness request, with up to 120 seconds for a sleeping instance. This is monitoring, not a keep-alive.
The artifact records response timings and failures; it does not claim a measured idle wake or answer quality.
Failed runs appear in GitHub Actions; GitHub notification delivery depends on the owner's account settings.

Every Sunday at 03:30 UTC (09:00 India time), a separate refresh job restores **registered** official PDFs and
checks each against its committed SHA-256. It then runs idempotent ingestion and rebuilds coverage and
QuarterLens snapshots. It needs the repository secret `SUPABASE_DB_URL`; this credential must remain private.
Jobs serialize so two refreshes cannot ingest the same new source concurrently.

The source checker permits only explicitly listed official HTTPS hosts, checks every redirect, bounds PDF size,
rejects HTML/errors/changed hashes and refuses to overwrite a different local PDF. An issuer blocking a download
or changing a PDF stops the refresh before database writes; the artifact lists the blocked files. Do not bypass
these checks or count an unavailable document as ingested. A local verified file can be used to complete the
same commands. Raw PDFs and secrets are never uploaded as workflow artifacts.

This job does **not** discover or approve new financial statements, roll the frozen corpus window forward,
extract new Growth Payoff projects, create predictions, generate evaluation labels or publish benchmarks.
Register additional sources only after checking issuer, document identity, fiscal period, call date and hash.
The frozen plan still has missing calls and should not be described as complete coverage.

Refreshed JSON files are downloadable review artifacts, not automatic public releases. Inspect and commit
them, pass CI, then deploy the reviewed main commit to Render and Vercel using [DEPLOYMENT.md](DEPLOYMENT.md).
This preserves the link between the public snapshot, source manifest and deployed revision.

Manual checks:

```bash
.venv/bin/python scripts/operations.py health --out /tmp/quantrag-health.json
.venv/bin/python scripts/operations.py sources --out /tmp/quantrag-sources.json
# With the private database environment supplied:
(cd backend && ../.venv/bin/python -m ingest.run)
.venv/bin/python eval/ingest_stats.py
.venv/bin/python scripts/build_company_monitor.py
.venv/bin/python scripts/export_public_data.py
```

The `sources` command checks supplemental results releases as well as transcripts. It does not contact pending
manifest rows or infer a source from a filename. A blocked refresh leaves the previous public snapshot intact.
An interruption after a per-document ingest commit can leave newly registered calls in the database before
snapshot publication; re-running ingestion skips those exact hashes and resumes safely.
