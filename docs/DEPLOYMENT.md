# Python deployment

## Vercel interface

`server.py` exports `streamlit.App` as an ASGI application; `api/index.py` exposes it to Vercel. `pyproject.toml` selects `api.index:app` as Vercel's entrypoint; root `requirements.txt` includes only UI dependencies. The FastAPI service can run alongside it as a Vercel container; Render remains the rollback host. There is no React/Next.js build.

Vercel project settings must use the repository root (not the removed `frontend` directory) with the old Next.js framework/build/install/output overrides cleared. The `web` service in `vercel.json` includes the Python dashboard and public snapshots in its function, excludes backend/private inputs, and sets the function duration to 300 seconds. The separate `analyst` container includes the API and model files.

Keep the existing `API_ORIGIN` for rollback and the server-only `API_ACCESS_TOKEN` on the Vercel project. The API token, database URL and Gemini settings must also be enabled for Preview to test live answers. Never print or commit their values. Snapshot browsing needs no API credentials.

Current Vercel supports Python ASGI WebSockets, but a serverless instance and its session state are temporary. A connection can close when the function duration ends; reconnects/refreshes may reset notes. Export research JSON before closing. This is a demo with no durable accounts or cross-device notes.

Deploy a preview and verify real browser interactions, source charts, JSON downloads and API requests before promoting. A successful build alone does not establish that WebSockets and Streamlit sessions work. Record actual release results in `docs/verification`.

References: https://vercel.com/docs/functions/websockets and https://docs.streamlit.io/develop/quick-reference/release-notes/2026.

## Render alternative and local containers

For a persistent Python server, `ui/Dockerfile` starts Streamlit on the host's `PORT` (default 8501). Set `API_ORIGIN` and the shared server-only `API_ACCESS_TOKEN`; only the API needs database and Gemini credentials.

For local containers, `docker compose up --build` starts both Python services. The UI is exposed on 8501; the API is internal. Budget state uses the existing named volume. No paid service is required or created by this configuration.

## Vercel API migration

`vercel.json` now defines `web` (Python ASGI Streamlit) and `analyst` (the container in root `Dockerfile.api`). Vercel Services and Container Runtime are beta. The container bakes the original FastEmbed/ONNX models into its image instead of downloading them on a user's request. Use project `PORT=8000`. The Dockerfile must remain at repository root because the container builder uses its directory as the build context.

Set `SUPABASE_DB_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, optional `GEMINI_FALLBACK_MODEL` and the existing `API_ACCESS_TOKEN` for Production and Preview. The UI selects the binding automatically when it is present; `API_PROVIDER=vercel` can require it explicitly. Vercel injects `ANALYST_INTERNAL_URL` from the service binding; never invent its value. Set `API_PROVIDER=local` to use `API_ORIGIN` for rollback. `/backend/health` and `/backend/docs` expose the API's read-only status/documentation; POST routes retain bearer authentication.

`Dockerfile.api` selects `USAGE_BACKEND=postgres` and `API_ROOT_PATH=/backend`. The first budget reservation safely creates the counter table with row-level security (versioned SQL in `db/migrations`). The database role must own that table and have permission to create it. Budget failures are closed with 503, exhausted quotas with 429. SQLite remains available for the original single-instance local/Render setup.

Keep Render available until the Vercel preview and production each return a real cited answer. Vercel also scales containers down after inactivity: measure an actual first request rather than promising zero cold starts. No paid plan is required by this configuration.

References: https://vercel.com/docs/services and https://vercel.com/docs/functions/runtimes/container.
