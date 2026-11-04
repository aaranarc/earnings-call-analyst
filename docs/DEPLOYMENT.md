# Python deployment

## Vercel interface

`server.py` exports `streamlit.App` as an ASGI application; `api/index.py` exposes it to Vercel. `pyproject.toml` selects `api.index:app` as Vercel's entrypoint; root `requirements.txt` includes only UI dependencies. The existing FastAPI service stays on Render. There is no React/Next.js build.

Vercel project settings must use the repository root (not the removed `frontend` directory) with the old Next.js framework/build/install/output overrides cleared. `vercel.json` includes the Python dashboard and public snapshots in the function, excludes backend/private inputs, and sets the function duration to 300 seconds.

Keep the existing production `API_ORIGIN` and server-only `API_ACCESS_TOKEN` on the Vercel project. Preview environments also need these values for live answers. Never print or commit their values. Snapshot browsing needs no API credentials.

Current Vercel supports Python ASGI WebSockets, but a serverless instance and its session state are temporary. A connection can close when the function duration ends; reconnects/refreshes may reset notes. Export research JSON before closing. This is a demo with no durable accounts or cross-device notes.

Deploy a preview and verify real browser interactions, source charts, JSON downloads and API requests before promoting. A successful build alone does not establish that WebSockets and Streamlit sessions work. Record actual release results in `docs/verification`.

References: https://vercel.com/docs/functions/websockets and https://docs.streamlit.io/develop/quick-reference/release-notes/2026.

## Render alternative and local containers

For a persistent Python server, `ui/Dockerfile` starts Streamlit on the host's `PORT` (default 8501). Set `API_ORIGIN` and the shared server-only `API_ACCESS_TOKEN`; only the API needs database and Gemini credentials.

For local containers, `docker compose up --build` starts both Python services. The UI is exposed on 8501; the API is internal. Budget state uses the existing named volume. No paid service is required or created by this configuration.
