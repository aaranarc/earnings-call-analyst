"""Load the real ONNX models once: the embedding size must match the schema, and the reranker must work.
Downloads ~200 MB on first run (cached in CI via FASTEMBED_CACHE_PATH)."""
import re
from pathlib import Path

import pytest

from retrieve.search import Models

SCHEMA = (Path(__file__).resolve().parents[2] / "db/schema.sql").read_text()


@pytest.fixture(scope="module")
def models():
    return Models(rerank=True)


def test_embedding_size_matches_schema(models):
    (dims,) = re.findall(r"embedding vector\((\d+)\)", SCHEMA)
    assert len(models.embed_query("What was TCS's operating margin?")) == int(dims)


def test_reranker_prefers_the_relevant_passage(models):
    q = "Why did the operating margin fall?"
    docs = ["Operating margins stood at 24%, down 130 bps sequentially, primarily due to wage hikes.",
            "We welcome our new chairman and thank the board for its guidance."]
    relevant, unrelated = models.reranker.rerank(q, docs, batch_size=models.rerank_batch)
    assert relevant > unrelated
