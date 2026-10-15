# Execution flow (traceability)

How a request or pipeline actually moves through the code, as ordered `file → function` chains. Update before and after every phase.

## Currently changing
**Phase 0:** no runtime path changes. Added `scripts/v1_baseline.py`, which imports v1's `RAGService` from an extracted `v1-final` copy and calls `ask()` / `retrieve_with_routing()` to measure them. The v1 paths below are documented as they exist at tag `v1-final`.

## v1 (tag `v1-final`)

### User asks a question (Streamlit → API)
1. `app/ui/streamlit_app.py` chat input → `requests.post(f"{API_URL}/ask", json={"question": ...}, timeout=120)`
2. `app/main.py: ask()` → `get_service()` (lazy singleton) → `RAGService.__init__` on first call: `load_dotenv`, Chroma `PersistentClient(chroma_db/)` or `HttpClient(CHROMA_HOST)`, `ChatGoogleGenerativeAI(model="gemini-3.1-flash-lite")`
3. `app/services/rag_service.py: RAGService.ask(question)`
   1. `retrieve_with_routing(question, n_results=5)`
      - `self.embeddings` (lazy `GoogleGenerativeAIEmbeddings("models/gemini-embedding-2")`) `.embed_query`
      - `get_corpus_summary()` → `collection.get()` (reads **all** metadata on every question) → unique company names
      - companies = names that appear as substrings of the lowercased question
      - ≥2 companies → one `collection.query(where={"company": c}, n_results=5 // len(companies))` per company, run in sequence
      - otherwise → one `collection.query`, filtered when exactly one company matched
   2. Build the context as `[company quarter year]: text` and the sources list (first 200 chars, deduplicated by company/quarter/year)
   3. f-string prompt → `self.llm.invoke([HumanMessage])` → return `{"answer", "sources"}`
4. Any exception → 500 with `str(e)` **and the full traceback** in the JSON body.

### Company list
`streamlit_app.py` → `GET /companies` → `main.get_companies()` → `svc.collection.get()` → set of (company, market, quarter, year).

### Risk score
`streamlit_app.py` (sidebar or tab 3) → `POST /risk-score` → `main.risk_score()` → `RAGService.predict_risk(financial_ratios?, company_name?)`
1. `_ensure_risk_models()` loads XGBoost `models/xgboost_bankruptcy.json` + scaler + winsorise bounds + feature names
2. Baseline for every feature = `0.45 + (sha256(company_name) % 10) / 100`
3. If a ticker is mapped: `yfinance.Ticker(t).info` → overwrite 4 features (debt ratio, ROA, operating margin, net-income flag)
4. Manual ratios override → clip → scale → `Booster.predict` → tier (>0.7 High, >0.3 Medium)
5. `shap.TreeExplainer` → top-3 features by |SHAP| share
6. If score > 0.3 and a company was given → `self.ask("Explain {company}'s {top_feature} ...")` for `rag_context`

### Ingestion (what built the shipped `chroma_db/`)
`re_ingest.py: main()` → `shutil.rmtree(chroma_db)` → `PersistentClient` → walk `data/**.pdf` → `PyMuPDFLoader` (per page) → `RecursiveCharacterTextSplitter(1000, 200)` → filename → metadata (`company` and `country` from folders; `quarter = parts[1]`, which is the market, so the real quarter is lost) → ids `{company}_{quarter}_{year}_{i}` (same for Q1 and Q2) → batches of 100: `GoogleGenerativeAIEmbeddings.embed_documents` → `collection.add` → `sleep(2)`. Per-file errors are caught and printed. Result: the index holds JPMorgan Q2 + 3 stubs.
`app/scripts/ingest.py` is an older, incompatible path (MiniLM 384-d into a Chroma server) and is not used.

### Deploy
`render.yaml`: two Docker services from the same `Dockerfile` (`python:3.11-slim`, `pip install -r requirements.txt`, `COPY . .`). The API runs `uvicorn app.main:app`, and the UI runs `streamlit run app/ui/streamlit_app.py` with `API_URL` pointing to the API service. The committed `chroma_db/` ships inside the image.
