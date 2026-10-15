"""Conservative thesis suggestions: exact quotes, correct period and human review."""
from generate import thesis
from retrieve.search import Hit


def hit(period="Q1 FY27"):
    return Hit(10, "TCS", "TCS", period, "CFO", "management", "prepared", 2,
               "Our operating margin was 24% after wage increases.")


class LLM:
    def __init__(self, result):
        self.result = thesis.Assessment(**result)

    def invoke(self, prompt):
        assert "Period under review" in prompt
        return self.result


def test_exact_source_evidence_returns_reviewable_suggestion():
    result = thesis.assess("Margins face wage pressure", [hit()], "Q1 FY27", LLM({
        "relation": "supports", "reason": "Wage increases accompanied the reported margin.",
        "evidence": [{"citation": 1, "quote": "Our operating margin was 24% after wage increases."}]}))
    assert result["relation"] == "supports"
    assert result["requires_review"] is True
    assert result["evidence"][0]["chunk_id"] == 10
    assert result["evidence"][0]["period"] == "Q1 FY27"


def test_hallucinated_quote_or_wrong_period_is_insufficient():
    for quote, citation, period in [("Revenue doubled.", 1, "Q1 FY27"),
                                    (hit().text, 9, "Q1 FY27"), (hit().text, 1, "Q2 FY27")]:
        result = thesis.assess("Margins recover", [hit()], period, LLM({
            "relation": "supports", "reason": "Model guess", "evidence": [{"citation": citation, "quote": quote}]}))
        assert result["relation"] == "insufficient"
        assert result["evidence"] == []


def test_missing_period_prevents_retrieval_and_generation(monkeypatch):
    import pytest
    monkeypatch.setattr(thesis, "coverage", lambda *a: {"TCS": ["Q1 FY27"]})
    monkeypatch.setattr(thesis, "retrieve", lambda *a, **k: pytest.fail("must not retrieve missing periods"))
    with pytest.raises(ValueError, match="not ingested"):
        thesis.check_thesis("Thesis", "TCS", ["Q4 FY26"], None, None)


def test_no_hits_is_insufficient_without_model_inference(monkeypatch):
    monkeypatch.setattr(thesis, "coverage", lambda *a: {"TCS": ["Q1 FY27"]})
    monkeypatch.setattr(thesis, "retrieve", lambda *a, **k: [])
    result = thesis.check_thesis("Thesis", "TCS", ["Q1 FY27"], None, None, llm=object())
    assert result["assessment"] == "Unresolved"
    assert result["automatic_status_change"] is False
    assert result["suggestions"][0]["relation"] == "insufficient"
