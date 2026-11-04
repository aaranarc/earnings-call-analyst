# Explain this version in an interview

The UI is Python Streamlit. You do not need React, Next.js, JavaScript or TypeScript to edit it. You still need to understand the backend and financial limitations; removing a technology does not remove it from an already-submitted resume.

## Read these files in order

1. `streamlit_app.py`: widgets, navigation and rendering. `st.title` draws text, `st.selectbox` returns a selected value, and `st.form_submit_button` triggers the API request. Plain functions divide the pages; there is no frontend build pipeline.
2. `ui/client.py`: one Python HTTP client. It submits a question with POST and reads status/answer/error events. Secrets remain on the server. `AnalystError` carries safe messages instead of printing network exceptions that could contain credentials.
3. `ui/research.py`: a note is a dictionary; saved notes are a list. JSON export turns that list into portable text. Import validation checks the expected fields before replacing the session's notes.
4. `backend/quantrag/api.py`: the existing FastAPI endpoints, Pydantic inputs, concurrency guard and pipeline calls.
5. `backend/retrieve/search.py`: vector search, keyword search, RRF and reranking.
6. `backend/generate/answer.py` and `backend/numcheck/match.py`: evidence-conditioned generation and numerical value matching.

## Streamlit concepts

**Reruns:** Streamlit executes the script again after most widget interactions. A form groups inputs so typing does not submit a question; expensive API work happens only when Ask or Retry is clicked.

**Session state:** `st.session_state` is a dictionary retained between reruns for that browser connection. It is not a database, user account, or durable backup. Notes start empty and can be exported; no shared server file mixes different people's notes.

**Charts:** Pandas represents rows in a table. Altair describes chart axes and marks from that table; Streamlit renders it. The source code is Python even though Streamlit internally renders a browser interface.

**HTTP and REST:** `ui/client.py` uses HTTPX to POST a JSON question to `/ask`. FastAPI validates the request; the UI reads a server-sent event stream. `/health` only reports configuration state and does not prove Gemini can answer.

**OOP:** `AnalystError` is a small exception class. The existing `Models` class groups loaded embedding/reranking models. We use classes where they help; we did not add layers merely to claim OOP.

**Testing:** HTTP-client tests simulate provider/API responses without calling paid services. Streamlit AppTest checks widget interactions and page rendering. Existing backend tests still test parsing, retrieval, numeric matching and API behaviour.

## Scenario arithmetic

`ui/research.py:project_payoff` multiplies an assumed investment by an assumed operating return and a linear ramp fraction. It reports annual incremental operating profit, not cumulative cash flow, stock prices or a trained prediction. Changing assumptions changes the chart; it does not discover the assumptions from historical data.

## Honest resume wording

“Built a Python Streamlit financial research dashboard backed by FastAPI and PostgreSQL/pgvector, with hybrid retrieval, Gemini-generated cited answers, numeric checks, reviewed quarterly charts and investment-milestone scenarios.”

If asked about an older React/Next.js resume: “The earlier interface used React/Next.js with AI assistance. I later rebuilt the interface in Python Streamlit so I could maintain and explain it myself.” Do not say the former interface never existed or that Streamlit demonstrates React experience.

## Five likely questions

1. Why Streamlit? It lets me build interactive pages in Python and reduces the frontend stack I need to maintain.
2. Why keep FastAPI? The same tested research pipeline remains available over HTTP, independent of the interface.
3. Where are notes stored? Only in this Streamlit session, with explicit JSON export/import; not in PostgreSQL.
4. Does a number match prove an answer is true? No. The value could refer to a different company, metric or period.
5. Is Growth Payoff a forecast? No. It is visible, user-selected scenario arithmetic next to reviewed milestones.

## Check your understanding

1. What happens when you click Ask, and which two files handle the UI and HTTP request?
2. Why should a user export their notes before closing the session?
3. Which parts of Growth Payoff are sourced facts, and which are assumptions?

## Matching the earlier visual design

`ui/presentation.py` holds the chart colours, coverage grid, sector ring and optional static styles. It has no JavaScript, React components or browser-side application logic. All forms, navigation, state and requests remain Python Streamlit. The static style block only changes appearance; removing it leaves the app functional.

`server.py` creates `streamlit.App`, an ASGI application, for a hosting platform to run. ASGI is the Python server interface also used by FastAPI; you do not need a Node build. The application still depends on a WebSocket connection, and serverless deployments can reconnect and lose session-only notes: export your notes regularly.

Existing `/ask`, `/watchlist`, `/growth-payoff`, `/research`, `/eval` and `/how-it-works` links redirect to a `page` query parameter. Python reads that parameter once to choose the initial sidebar page. Clicking navigation still uses ordinary Streamlit session state; there is no client router to maintain.

On Vercel, `server.py` supplies the same theme through environment defaults because hidden config-file discovery differs from a local launch. Research exports are encoded as a direct download link in `ui/presentation.py`, so they do not depend on a temporary server media file. Restore research by opening the downloaded JSON and pasting its contents into Import a backup; this avoids server-local upload state. No JavaScript is used. Charts may take an extra moment to load their built-in rendering code on a fresh browser visit.
