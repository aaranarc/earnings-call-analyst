"""Offline tests use synthetic fixture judgments; no benchmark labels are created."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "eval"))
from generation_eval import summarize
from publish_eval import agreement, build_report


def row(i, answerable=True, refused=False, faithful=True, correct=True):
    return {"id": str(i), "answerable": answerable,
            "answer": {"refused": refused, "timing_s": {"total": 2}, "numbers": [{"status": "verified"}]},
            "judge": {"faithful": faithful, "correct": correct}}


def test_refusal_and_faithfulness_have_distinct_denominators():
    stats = summarize([row(1), row(2, answerable=False, refused=True), row(3, faithful=False, correct=False)])
    assert stats["faithfulness"] == 0.5
    assert stats["refusal_accuracy"] == 1
    assert stats["correctness"] == pytest.approx(2 / 3)
    assert stats["number_value_match_rate"] == 1  # not semantic numeric precision
    assert summarize([row(1, answerable=False, refused=True)])["faithfulness"] is None


def test_human_agreement_excludes_unsure_and_handles_degenerate_kappa():
    rows = [row(1), row(2, faithful=False), row(3)]
    labels = [{"id": "1", "faithful": "supported", "reviewed_by": "human"},
              {"id": "2", "faithful": "not_supported", "reviewed_by": "human"},
              {"id": "3", "faithful": "unsure", "reviewed_by": "human"}]
    got = agreement(rows, labels)
    assert got["kappa"] == 1 and got["sample_size"] == 2 and got["unsure"] == 1
    assert agreement([row(1)], labels[:1])["kappa"] is None
    with pytest.raises(ValueError):
        agreement(rows, labels[:1])


def test_publisher_refuses_mismatched_runs_and_small_sets():
    gen = {"gold_sha256": "a", "corpus": [], "rows": [row(1)]}
    with pytest.raises(ValueError, match="frozen gold"):
        build_report(gen, {"gold_sha256": "b", "corpus": []}, [])
    with pytest.raises(ValueError, match="60 reviewed"):
        build_report(gen, {"gold_sha256": "a", "corpus": []}, [])
