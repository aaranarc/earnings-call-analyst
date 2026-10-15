# QuantRAG release and deployment

The dashboard and API have separate runtime containers. The current hosting choice is deliberately deferred
until the owner reviews the release checks. Nothing in these files provisions a paid service automatically.

## Local production preview

Use `.env` for API database/model settings. Generate a shared token without posting it to chat:

```bash
# Add the output locally as API_ACCESS_TOKEN in .env and frontend/.env.local.
python3 -c 'import secrets; print(secrets.token_urlsafe(32))'
```

Add `APP_ENV=production`, `PUBLIC_ORIGIN=http://localhost:3000` and the token to `.env`, then:

```bash
docker compose --env-file .env up --build
```

Open http://localhost:3000. The API is available only on the internal Compose network. Its model files are
included in the image. The usage volume survives container recreation. Do not mount a production database
into the test suite: DB integration tests drop the `quantrag` schema in `quantrag_test` only.

## Hosting options

- **Free web frontend + free Render API:** deploy the Next.js `frontend/` project to a Node/Next.js host,
  with runtime `API_ORIGIN=https://<your-api>.onrender.com`, `API_ACCESS_TOKEN` matching the API,
  and `PUBLIC_ORIGIN=https://<your-web-host>`. The Next server calls the API; the token never reaches the browser.
  Render free APIs sleep after 15 minutes idle and can take about a minute to wake. The dashboard itself can
  stay independently available; live queries show progress/retry while the API wakes.
- **Always-on API:** a paid Render compute instance avoids idle spin-down. Choose memory based on the Linux
  container measurement, not the older macOS RSS result. Confirm current pricing before provisioning.
- **Cloud Run:** the same container works with the injected `PORT`; avoiding scale-to-zero requires warm
  minimum instances and incurs charges. Multiple instances need a shared usage budget rather than local SQLite.

References: [Render free limits](https://render.com/docs/free), [Render blueprint specification](https://render.com/docs/blueprint-spec),
[Cloud Run pricing](https://cloud.google.com/run/pricing).

The checked-in `render.yaml` configures only the API free option. It replaces the legacy v1 Streamlit blueprint.
Model credentials and the database URL are entered as secret environment values. The web token must match the
Render-generated API token; do not put any token in a `NEXT_PUBLIC_` variable.

## Usage and access controls

- Production startup fails unless `API_ACCESS_TOKEN` is at least 32 characters. Paid endpoints reject missing
  or incorrect Bearer tokens. Public health/coverage/eval endpoints disclose no credentials.
- Next allows only known API routes/methods and bounded request bodies; rejects explicit cross-origin POSTs;
  forwards only a server-configured credential. Its configured API origin is never user-controlled.
- `DAILY_REQUEST_LIMIT` defaults to 100 request units in UTC. Each thesis period consumes one unit. A reservation
  is counted even if a provider call fails. This caps attempts, not dollars; provider token billing is separate.
- One in-flight model request per API process returns 429 while busy. Model output is bounded and provider
  timeouts are configured. An API instance runs one worker to bound memory and avoid duplicate model loads.
- SQLite budget updates are transactional across processes sharing the same file. `USAGE_DB_PATH` must point
  to a persistent mounted directory for a quota that survives restarts. Free Render's ephemeral filesystem
  resets on redeploy/replacement: this option's budget is instance-lifetime protection, not a durable billing cap.
  Set provider billing limits too. Use a persistent disk or shared quota store before promising a durable cap.
- Research stays browser-local. JSON export/import provides backups; no accounts or cross-device sync are claimed.

## Release checks and rollback

```bash
.venv/bin/ruff check backend scripts eval --config backend/pyproject.toml
.venv/bin/python -m pytest -c backend/pyproject.toml backend/tests scripts -q
npm ci --prefix frontend
npm run build --prefix frontend
npm run test:e2e --prefix frontend
docker build -t quantrag-api:release .
docker build -t quantrag-web:release frontend
```

Verify `/health`, real cited answers, missing-quarter refusals, and a thesis suggestion before opening a hosted
release. Public benchmark metrics remain pending until the human gold and judge calibration are complete.
Revert to the previous deployment image/commit for rollback; no user-data schema migration is required by this
release. Browser v1 data remains as a migration backup. Keep JSON exports before changing browsers or clearing data.

## Data and evaluation dependencies

Official source candidates are recorded in `data/source_candidates.json`. Direct PDF downloads returned 403;
these locations are not counted as ingested coverage. Once PDFs are available, verify identity, quarter, date,
and SHA-256, register them in the manifest, run the manifest checker, dry-run parsing, then ingest, refresh
`eval/results/ingest_stats.json`, and run `python scripts/export_public_data.py` before deploying the web app. Gate A remains all 12 companies × latest 4 quarters.

Phase 6 tools are documented in [EVALUATION.md](EVALUATION.md). Human review is a real dependency, not a flag the
agent can truthfully set for itself. The deferred Phase 5 blind labels and Nestlé count remain owner tasks.
