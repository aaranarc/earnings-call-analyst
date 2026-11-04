# Current implementation decisions

- Replace the custom JavaScript frontend with Streamlit so the owner can study and maintain one UI language: Python.
- Keep the FastAPI research pipeline and PostgreSQL schema intact; no new authentication framework or database layer.
- Keep committed snapshots for offline source browsing. Move their location from frontend/lib to ui/data and update producer/check scripts.
- Keep notes isolated in session state with explicit JSON export/import. No durable-storage claim.
- Use native Python widgets and Altair charts. Margin values are dots on one selected basis, preventing an invented continuous trend across missing periods.
- Replace removed Playwright UI checks with Streamlit AppTest plus HTTP-client tests. Past browser-test results are historical.

Earlier decisions and the original interface are described in docs/history/DECISIONS.md.
