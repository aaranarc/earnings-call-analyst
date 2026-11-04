"""Vercel Python function entrypoint; reuses the same ASGI app as local Uvicorn."""
from server import app  # noqa: F401 -- Vercel imports this ASGI object
