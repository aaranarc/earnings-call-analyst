# Local development

Follow the two-terminal commands in the root README. Python 3.11 is the supported baseline; Node/npm are not required.

- Dashboard: `python -m streamlit run streamlit_app.py` (8501).
- API: `python -m uvicorn quantrag.api:app --app-dir backend --env-file .env --host 127.0.0.1 --port 8000`.
- A local UI may point to a separately hosted API by setting `API_ORIGIN` on its server.
- The backend requires an ingested PostgreSQL database, Gemini credentials and its existing model dependencies for live answering. Browse snapshots offline while preparing those.
- `.env`, `.streamlit/secrets.toml` and downloaded PDFs are excluded from version control.

To ingest, obtain only the registered official PDFs, validate `data/manifest.csv` with `python scripts/check_manifest.py --gate phase2`, then run `PYTHONPATH=backend python -m ingest.run`. Do not point database tests at this database. The optional tests in `backend/tests/test_ingest_db.py` require a separate localhost `TEST_DATABASE_URL` and reset its schema.

Snapshot checks:

```bash
python scripts/build_company_monitor.py --check
python scripts/build_growth_payoff.py --check
python scripts/export_public_data.py --check
python scripts/export_development_results.py --check
python scripts/save_example_answers.py --check
```

Regeneration may need registered raw PDFs and database access; checks of committed output do not. Run Streamlit AppTest and HTTP-client tests with `pytest ui/tests -q`. Existing backend tests remain independent of the UI.
