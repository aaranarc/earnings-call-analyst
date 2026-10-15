"""Ingestion against a real Postgres + pgvector. Skipped unless TEST_DATABASE_URL points at a LOCAL database,
because the test drops and recreates the quantrag schema.

    docker run -d --name qr-pg -e POSTGRES_PASSWORD=pg -p 5433:5432 pgvector/pgvector:pg17
    TEST_DATABASE_URL=postgresql://postgres:pg@localhost:5433/postgres pytest tests/test_ingest_db.py
"""
import os
from urllib.parse import urlparse

import numpy as np
import pytest

URL = os.environ.get("TEST_DATABASE_URL", "")
pytestmark = pytest.mark.skipif(
    urlparse(URL).hostname not in ("localhost", "127.0.0.1"),
    reason="needs TEST_DATABASE_URL on localhost (the test drops the quantrag schema)",
)

COMPANIES = "- {symbol: TCS, name: Tata Consultancy Services, sector: it_services, aliases: [TCS]}\n"


class FakeEmbedder:
    def count(self, text):
        return len(text.split())

    def embed(self, texts):
        return [np.full(384, (i + 1) / 1000, dtype=np.float32) for i, _ in enumerate(texts)]


@pytest.fixture
def setup(tmp_path, monkeypatch):
    import psycopg

    import check_manifest as cm
    from ingest import run
    from ingest.parse import Turn

    (tmp_path / "companies.yaml").write_text(COMPANIES)
    (tmp_path / "raw").mkdir()
    pdf = tmp_path / "raw" / "TCS_Q1FY27.pdf"
    pdf.write_bytes(b"%PDF-1.4 stand-in; parsing is replaced below")
    cm.write_manifest(tmp_path / "manifest.csv", [{
        "symbol": "TCS", "fiscal_label": "Q1 FY27", "period_end": "2026-06-30", "call_date": "2026-07-09",
        "source_url": "https://example.com/tcs.pdf", "filename": pdf.name, "sha256": cm.sha256(pdf)}])
    turns = [Turn("K Krithivasan", "management", "prepared", 2, "Revenue stood at ₹72,275 crore, up 2.2%.", [(0, 2)]),
             Turn("Kumar Rakesh", "analyst", "qa", 9, "What is the margin outlook after the wage hike?", [(0, 9)]),
             Turn("Samir Seksaria", "management", "qa", 9, "Margins were 24%, down 130 bps on wage hikes.", [(0, 9)])]
    monkeypatch.setattr(run, "parse_transcript", lambda path: turns)

    conn = psycopg.connect(URL, options="-c search_path=quantrag,public,extensions")
    conn.execute("drop schema if exists quantrag cascade")
    conn.commit()
    yield conn, lambda: run.ingest(conn, tmp_path / "manifest.csv", tmp_path / "companies.yaml", tmp_path / "raw",
                                   embedder_factory=FakeEmbedder, log=lambda *_: None)
    conn.close()


def counts(conn):
    return conn.execute("""select (select count(*) from companies), (select count(*) from documents),
                                  (select count(*) from chunks), (select count(*) from chunk_numbers)""").fetchone()


def test_ingest_writes_document_chunks_and_numbers(setup):
    conn, ingest = setup
    assert ingest()["documents"] == 1
    assert counts(conn) == (1, 1, 3, 4)  # ₹72,275 crore, 2.2%, 24%, 130 bps; the question has none
    roles = conn.execute("select speaker, role, section, page from chunks order by id").fetchall()
    assert roles[1] == ("Kumar Rakesh", "analyst", "qa", 9)
    (unit, value), = conn.execute("select unit, value from chunk_numbers where raw like '%%crore'").fetchall()
    assert (unit, value) == ("INR", 7.2275e11)
    (dims,) = conn.execute("select vector_dims(embedding) from chunks limit 1").fetchone()
    assert dims == 384


def test_second_run_adds_nothing(setup):
    conn, ingest = setup
    ingest()
    before = counts(conn)
    assert ingest()["documents"] == 0
    assert counts(conn) == before


def test_keyword_column_is_generated(setup):
    conn, ingest = setup
    ingest()
    (hits,) = conn.execute("select count(*) from chunks where tsv @@ websearch_to_tsquery('english', 'wage hikes')"
                           ).fetchone()
    assert hits == 2
