"""Generation logic with a fake LLM and fake retrieval: no API calls, no database."""
from pathlib import Path

import check_manifest as cm
import pytest

import generate.answer as ga
from generate.answer import LLMAnswer, validate
from retrieve.search import Hit

COMPANIES, _ = cm.load_companies(Path(cm.ROOT) / "data/companies.yaml")


def hit(i, sym="TCS"):
    return Hit(i, sym, COMPANIES[sym]["name"], "Q1 FY27", "K Krithivasan", "management", "prepared", 2,
               f"Revenue grew 2.2% [{i}]", {"rerank": 1.0})


class FakeLLM:
    def __init__(self, ans):
        self.ans, self.calls = ans, []

    def invoke(self, prompt):
        self.calls.append(prompt)
        return self.ans


@pytest.fixture
def wired(monkeypatch):
    cov = {"TCS": ["Q1 FY27"], "INFY": ["Q2 FY25"]}
    monkeypatch.setattr(ga, "coverage", lambda conn, symbols=None: {s: v for s, v in cov.items()
                                                                     if not symbols or s in symbols})
    state = {"hits": [hit(101), hit(102), hit(103, "INFY")]}
    monkeypatch.setattr(ga, "retrieve", lambda *a, **k: state["hits"])
    return state


def run(q, llm):
    return ga.answer(q, conn=None, models=None, companies=COMPANIES, llm=llm)


def test_invalid_citation_markers_are_dropped():
    ans, cited = validate(LLMAnswer(answer_markdown="Revenue grew [c2]. Margin fell [c9][c1]."), n=3)
    assert ans.answer_markdown == "Revenue grew [c2]. Margin fell [c1]."
    assert cited == [2, 1]


def test_table_cell_with_bad_citation_becomes_not_discussed():
    raw = LLMAnswer(answer_markdown="See table [c1].", comparison_table=[
        {"metric": "TCV", "cells": [{"company": "TCS", "value": "$9.5 billion", "citations": [1]},
                                    {"company": "Infosys", "value": "$2.4 bn", "citations": [7]}]}])
    ans, cited = validate(raw, n=3)
    cells = ans.comparison_table[0].cells
    assert (cells[0].value, cells[1].value, cells[1].citations) == ("$9.5 billion", "not discussed", [])
    assert cited == [1]


def test_cited_answer_maps_citations_to_chunks(wired):
    llm = FakeLLM(LLMAnswer(answer_markdown="TCS revenue grew 2.2% [c1]. Infosys grew [c3]."))
    out = run("Compare TCS and Infosys revenue growth", llm)
    assert not out["refused"]
    assert [(c["n"], c["chunk_id"], c["symbol"]) for c in out["citations"]] == [(1, 101, "TCS"), (3, 103, "INFY")]
    assert "[c1]" in llm.calls[0] and "Tata Consultancy Services · Q1 FY27 · K Krithivasan" in llm.calls[0]
    assert "comparison_table" in llm.calls[0]  # comparison rule included in the prompt


def test_answer_without_valid_citations_is_withheld(wired):
    out = run("What did TCS say about AI?", FakeLLM(LLMAnswer(answer_markdown="TCS is doing well [c9].")))
    assert out["refused"] and "no valid citations" in out["refusal_reason"]


def test_model_refusal_lists_what_is_available(wired):
    llm = FakeLLM(LLMAnswer(answer_markdown="", refused=True, refusal_reason="No dividend figure in the excerpts"))
    out = run("What dividend did TCS declare?", llm)
    assert out["refused"]
    assert out["refusal_reason"].startswith("No dividend figure in the excerpts.")
    assert "Tata Consultancy Services: Q1 FY27" in out["refusal_reason"]


def test_no_hits_refuses_without_calling_the_llm(wired):
    wired["hits"] = []
    llm = FakeLLM(None)
    out = run("What did Wipro say about deal wins?", llm)
    assert out["refused"] and "Wipro: no transcripts ingested yet" in out["refusal_reason"]
    assert llm.calls == []


def test_out_of_scope_refuses_without_retrieval_or_llm(wired, monkeypatch):
    monkeypatch.setattr(ga, "retrieve", lambda *a, **k: pytest.fail("should not retrieve"))
    llm = FakeLLM(None)
    out = run("What's the weather in Mumbai?", llm)
    assert out["refused"] and out["route"]["kind"] == "out_of_scope" and llm.calls == []
    assert "Infosys (Q2 FY25)" in out["refusal_reason"]


def test_risk_answers_say_ews_is_not_connected(wired):
    out = run("Is there any default risk at TCS?", FakeLLM(LLMAnswer(answer_markdown="No stress flagged [c1].")))
    assert "early-warning system aren't connected yet" in out["answer_markdown"]


def test_rerank_floor_refuses_weak_matches(wired, monkeypatch):
    monkeypatch.setenv("REFUSAL_MIN_RERANK", "5.0")  # every fake hit scores 1.0
    llm = FakeLLM(None)
    out = run("What did TCS say about AI?", llm)
    assert out["refused"] and llm.calls == []


def test_table_only_kept_for_comparisons(wired):
    table = [{"metric": "TCV", "cells": [{"company": "Infosys", "value": "$2.4 bn", "citations": [3]}]}]
    out = run("How many large deals did Infosys win?",
              FakeLLM(LLMAnswer(answer_markdown="21 deals [c3].", comparison_table=table)))
    assert out["comparison_table"] is None
    out = run("Compare TCS and Infosys on deals",
              FakeLLM(LLMAnswer(answer_markdown="See [c3].", comparison_table=table)))
    assert out["comparison_table"][0]["cells"][0]["value"] == "$2.4 bn"
