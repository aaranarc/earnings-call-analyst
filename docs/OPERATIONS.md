# Operations after the Python UI migration

Existing source recovery and ingestion procedures still apply to the API. The weekly workflow now exports public snapshots into `ui/data/public-data.json`.

The readiness script checks Vercel's Streamlit `/_stcore/health` endpoint, and reads coverage/evaluation directly from the existing Render API. It no longer depends on the removed Next.js `/api` proxy. These HTTP checks are not a substitute for a browser session and a real cited answer.

Daily API request counts are stored in SQLite by `backend/quantrag/usage.py`. They are a request budget, not precise monetary billing. A persistent volume is needed to retain them across container replacement.

See docs/history/OPERATIONS.md for earlier operational history, not current UI deployment instructions.
