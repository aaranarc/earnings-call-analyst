"""Offline checks with synthetic evidence; never loads human labelling keys."""
import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

spec = importlib.util.spec_from_file_location("retrieval_eval", Path(__file__).parents[1] / "eval/retrieval_eval.py")
ev = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ev)


def gold():
    return {"id": "g01", "question": "Synthetic question?", "human_verified": True,
            "reviewed_by": "test fixture", "answerable": True,
            "evidence": [{"symbol": "TEST", "fiscal_label": "Q1 FY27", "quotes": ["alpha", "alternate"]},
                         {"symbol": "TEST", "fiscal_label": "Q1 FY27", "quotes": ["beta"]}]}


def hit(text, symbol="TEST"):
    return SimpleNamespace(text=text, symbol=symbol, fiscal_label="Q1 FY27", chunk_id=1)


def test_scoring_separates_first_hit_from_completeness():
    scored = ev.score(gold(), [hit("irrelevant"), hit("alternate"), *[hit("irrelevant")] * 3, hit("beta")])
    assert scored == {"evidence_ranks": [2, 6], "hit_at_5": True,
                      "mrr_at_10": 0.5, "completeness_at_5": 0.5}


def test_evidence_requires_correct_company_and_top_ten():
    assert ev.score(gold(), [hit("alpha beta", "WRONG")])["mrr_at_10"] == 0
    assert ev.score(gold(), [hit("none")] * 10 + [hit("alpha beta")])["mrr_at_10"] == 0
    assert ev.score(gold(), [hit("alpha beta")])["completeness_at_5"] == 1


def test_unanswerable_excluded_from_retrieval_denominator():
    item = {**gold(), "answerable": False, "evidence": []}
    rows = [{**ev.score(item, []), "elapsed_s": 0.2},
            {**ev.score(gold(), []), "elapsed_s": 0.4}]
    summary = ev.summarize(rows)
    assert summary["questions"] == 2
    assert summary["answerable_questions"] == 1
    assert summary["hit_at_5"] == 0
    assert ev.summarize(rows[:1])["mrr_at_10"] is None


@pytest.mark.parametrize("change", [
    {"human_verified": False}, {"reviewed_by": " "}, {"answerable": "yes"},
    {"evidence": []}, {"evidence": [{"symbol": "TEST", "fiscal_label": "Q1 FY27", "quotes": [""]}]},
])
def test_invalid_gold_rejected(tmp_path, change):
    path = tmp_path / "gold.jsonl"
    path.write_text(json.dumps({**gold(), **change}) + "\n")
    with pytest.raises(ValueError, match="gold line 1"):
        ev.load_gold(path)


def test_duplicate_questions_and_empty_gold_rejected(tmp_path):
    path = tmp_path / "gold.jsonl"
    path.write_text("")
    with pytest.raises(ValueError, match="empty"):
        ev.load_gold(path)
    path.write_text(json.dumps(gold()) + "\n")
    assert len(ev.load_gold(path)) == 1
    with path.open("a") as out:
        out.write(json.dumps({**gold(), "id": "g02"}) + "\n")
    with pytest.raises(ValueError, match="duplicate question"):
        ev.load_gold(path)


def test_corpus_percent_not_a_wildcard():
    conn = SimpleNamespace(execute=lambda *args: SimpleNamespace(fetchall=lambda: [("margin 15 percent",)]))
    item = {**gold(), "evidence": [{"symbol": "TEST", "fiscal_label": "Q1 FY27", "quotes": ["15%"]}]}
    with pytest.raises(ValueError, match="absent"):
        ev.validate_corpus(conn, [item])


def test_router_filters_and_global_ranking(monkeypatch):
    import generate.router
    import retrieve.search

    calls = []
    monkeypatch.setattr(generate.router, "route", lambda *a, **kw: SimpleNamespace(
        kind="comparison", companies=["A", "B"], periods=["Q1 FY27"]))
    monkeypatch.setattr(retrieve.search, "retrieve", lambda *a, **kw: calls.append(kw) or [])
    ev.run_config(None, None, [gold()], {}, {}, "hybrid", False, True)
    assert calls[0]["companies"] == ["A", "B"]
    assert calls[0]["split_by_company"] is False
    assert calls[0]["top_n"] == 10
