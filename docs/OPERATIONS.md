# Operations after the Python UI migration

Existing source recovery and ingestion procedures still apply to the API. The weekly workflow now exports public snapshots into `ui/data/public-data.json`.

The readiness script and older production checks still target the previous public deployment. They do not prove the local Streamlit interface is deployed. Update service URLs only after a real Streamlit deployment; the existing production installation has not been changed here.

Daily API request counts are stored in SQLite by `backend/quantrag/usage.py`. They are a request budget, not precise monetary billing. A persistent volume is needed to retain them across container replacement.

See docs/history/OPERATIONS.md for earlier operational history, not current UI deployment instructions.
