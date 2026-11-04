# The current request flow

1. `streamlit_app.py` draws widgets in Python. Streamlit reruns it when a user interacts. `st.session_state` keeps the current answer and notes between reruns.
2. The Ask form calls `ui/client.py:ask`. HTTPX sends JSON to FastAPI's `/ask`. The secret comes from the Streamlit server environment, never from a browser widget.
3. `backend/quantrag/api.py` validates the question and checks its existing access token, concurrency lock and request budget. It sends progress events while the blocking research function runs in a thread pool.
4. `backend/generate/router.py` identifies covered companies and periods. `backend/retrieve/search.py` combines PostgreSQL vector and keyword search, merges rankings with RRF and reranks candidates using ONNX.
5. `backend/generate/answer.py` asks Gemini for a structured answer from retrieved context. `backend/numcheck/match.py` checks numerical values against source material. Reference validation is not full semantic verification.
6. `ui/client.py` reads server-sent events. The UI renders Markdown, a comparison table, number statuses and expandable source excerpts. Failed requests offer dated examples; they are never labelled live.

Offline pages load reviewed JSON from `ui/data`. Export scripts regenerate or validate those files. `ui/research.py` contains only note validation and the explicit linear-ramp scenario arithmetic; it does not call an AI model or database.

The former Next.js architecture is preserved only as historical documentation in `docs/history`.
