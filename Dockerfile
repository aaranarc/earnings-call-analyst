FROM python:3.11-slim AS build
WORKDIR /app
COPY backend/requirements-api.lock ./requirements-api.lock
RUN pip install --no-cache-dir --prefix=/install -r requirements-api.lock

FROM python:3.11-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 FASTEMBED_CACHE_PATH=/app/models \
    OMP_NUM_THREADS=2 TOKENIZERS_PARALLELISM=false APP_ENV=production
WORKDIR /app
RUN useradd --create-home --uid 10001 analyst && mkdir -p /app/usage
COPY --from=build /install /usr/local
COPY backend/ backend/
COPY scripts/check_manifest.py scripts/check_manifest.py
COPY data/companies.yaml data/manifest.csv data/
COPY eval/results/ingest_stats.json eval/results/ingest_stats.json
# Ship models with the image so a cold request never downloads them.
RUN PYTHONPATH=backend python -c 'from retrieve.search import Models; Models(rerank=True)' && chown -R analyst:analyst /app
ENV HF_HUB_OFFLINE=1
USER analyst
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"
CMD ["sh", "-c", "exec uvicorn quantrag.api:app --app-dir backend --host 0.0.0.0 --port ${PORT:-8000} --workers 1 --no-proxy-headers"]
