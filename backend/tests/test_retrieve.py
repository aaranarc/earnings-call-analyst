import pytest

from retrieve.search import Hit, rrf


def hits(*ids, stage):
    return [Hit(i, "TCS", "TCS", "Q1 FY27", "x", "management", "qa", 1, f"text {i}",
                {stage: 1.0 / r, f"{stage}_rank": r}) for r, i in enumerate(ids, start=1)]


def test_rrf_hand_example():
    # dense ranks: a=1 b=2 c=3 ; fts ranks: c=1 a=2 d=3   (k=60)
    fused = rrf([hits("a", "b", "c", stage="dense"), hits("c", "a", "d", stage="fts")], k=60)
    expected = {"a": 1 / 61 + 1 / 62, "c": 1 / 63 + 1 / 61, "b": 1 / 62, "d": 1 / 63}
    assert [h.chunk_id for h in fused] == ["a", "c", "b", "d"]
    for h in fused:
        assert h.scores["rrf"] == pytest.approx(expected[h.chunk_id])
    assert [h.scores["rrf_rank"] for h in fused] == [1, 2, 3, 4]


def test_rrf_keeps_every_stage_score_for_the_ui():
    a = rrf([hits("a", stage="dense"), hits("a", stage="fts")])[0]
    assert {"dense", "dense_rank", "fts", "fts_rank", "rrf", "rrf_rank"} <= a.scores.keys()


def test_rrf_with_one_empty_list_is_that_list_order():
    assert [h.chunk_id for h in rrf([hits("x", "y", stage="dense"), []])] == ["x", "y"]
