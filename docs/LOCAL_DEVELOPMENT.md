# Local development

[← Back to the README](../README.md)

Use Python 3.11, Node.js 22 and npm. A full installation also needs a PostgreSQL database with pgvector, a Gemini API key and locally downloaded source PDFs. Docker is optional for a local database or production preview.

## 1. Install the backend

From the repository root:

```bash
python3.11 -m venv .venv
.venv/bin/pip install -c backend/requirements-api.lock -e "backend[dev,api]"
cp .env.example .env
```

Edit `.env`: set `SUPABASE_DB_URL`, `GEMINI_API_KEY` and `GEMINI_MODEL`. Use a database you own. Leave `APP_ENV=development` for loopback development. The optional `GEMINI_FALLBACK_MODEL` is an explicit provider choice; configure a model available to your account.

Never commit `.env`, database credentials or API tokens. Frontend credentials must remain server-only, without a `NEXT_PUBLIC_` prefix.

For a local database:

```bash
docker run -d --name qr-pg -e POSTGRES_PASSWORD=pg \
  -p 127.0.0.1:5433:5432 pgvector/pgvector:pg17
```

Set `SUPABASE_DB_URL=postgresql://postgres:pg@localhost:5433/postgres` in `.env` when using that container. The ingestion command applies the idempotent schema, including the vector extension; the database user needs permission to create it.

## 2. Supply and ingest source documents

PDFs are excluded from Git. Use the official URLs and exact filenames in [`data/manifest.csv`](../data/manifest.csv), saving downloaded transcripts under `data/raw/`. Preserve the registered source URL, company, fiscal period and SHA-256. Missing quarters are pending coverage, not empty financial results.

With enough registered PDFs for the initial sector gate:

```bash
.venv/bin/python scripts/check_manifest.py --gate phase2

# Export your locally configured variables for ingestion.
set -a
source .env
set +a

cd backend
../.venv/bin/python -m ingest.run
cd ..
```

The check reports missing or mismatched files. Do not replace a registered hash just to make a changed download pass. For newly reviewed sources, see the [operations guide](OPERATIONS.md). The private recovery archive used by the deployed project is not a public download service.

Ingestion skips documents already stored with the same hash. The first run downloads embedding models. Reranking models load on the answer path and also need download access on first use.

After an intentional corpus update, rebuild and review dashboard snapshots:

```bash
.venv/bin/python eval/ingest_stats.py
.venv/bin/python scripts/build_company_monitor.py
.venv/bin/python scripts/export_public_data.py
```

Growth Payoff has a separate reviewed source definition; `scripts/build_growth_payoff.py --check` validates its current snapshot. Adding transcripts does not automatically create investment milestones.

## 3. Start the API and dashboard

From the repository root, in one terminal:

```bash
.venv/bin/python -m uvicorn quantrag.api:app --app-dir backend \
  --env-file .env --host 127.0.0.1 --port 8000
```

In a second terminal:

```bash
cd frontend
cp .env.example .env.local
npm ci
npm run dev
```

Open **http://127.0.0.1:3000**. The Next.js server proxies live requests to the local API. If you configure an `API_ACCESS_TOKEN`, use the same value in both servers. Only the Python API receives database and Gemini credentials.

The browser receives progress events followed by a fully checked answer, rather than unchecked model tokens. Empty databases cannot answer questions; the checked-in coverage view is a published snapshot, not proof that your local database is populated.

For a terminal demo, from the repository root:

```bash
.venv/bin/python -m quantrag.ask "What net interest margin did Kotak Mahindra Bank report in Q1 FY27?"
```

## 4. Verify changes

Backend lint and tests, from the repository root:

```bash
.venv/bin/ruff check backend scripts eval --config backend/pyproject.toml
cd backend
../.venv/bin/python -m pytest tests ../scripts -q
cd ..
```

Database integration tests need a **separate throwaway localhost database** and skip when it is not configured. They drop the `quantrag` schema in that test database. Never point them at your development or production data.

```bash
docker exec qr-pg psql -U postgres -c "create database quantrag_test"
cd backend
TEST_DATABASE_URL=postgresql://postgres:pg@localhost:5433/quantrag_test \
  ../.venv/bin/python -m pytest tests ../scripts -q
cd ..
```

Frontend checks:

```bash
cd frontend
npm run build
npm run typecheck
npm run test:e2e
```

The local Playwright configuration uses installed Google Chrome; CI installs Chromium. Tests include mobile layouts, evidence workflows and automated accessibility checks. See the [CI workflow](../.github/workflows/ci.yml) for the complete current release checks and coverage command.

Install the existing secret-scanning push hook once per clone (example for macOS with Homebrew):

```bash
brew install gitleaks
git config core.hooksPath .githooks
```

The hook fails closed if Gitleaks is unavailable. Do not publish raw PDFs, local credentials, browser research exports or private blind-evaluation material.

## Production and evaluation

- [Deployment](DEPLOYMENT.md): Docker Compose preview, Vercel/Render configuration, access controls and free-hosting limits. A Git push currently does not automatically redeploy the public services.
- [Operations](OPERATIONS.md): registered-source recovery, daily readiness and weekly refreshes.
- [Evaluation](EVALUATION.md): human review, frozen gold data, ablations and deliberate score publication.
