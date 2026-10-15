from pathlib import Path

import check_manifest as cm
import pytest

from generate.router import route

COMPANIES, _ = cm.load_companies(Path(cm.ROOT) / "data/companies.yaml")
LATEST = {"TCS": "Q1 FY27", "INFY": "Q1 FY27", "HDFCBANK": "Q1 FY27", "HINDUNILVR": "Q1 FY27", "ITC": "Q4 FY26"}


def r(q, **kw):
    return route(q, COMPANIES, LATEST, enabled=True, **kw)


@pytest.mark.parametrize("q, kind, companies", [
    ("What did TCS say about deal wins?", "single", ["TCS"]),
    ("What did Tata Consultancy Services say about AI?", "single", ["TCS"]),
    ("Compare TCS and Infosys on margins", "comparison", ["TCS", "INFY"]),
    ("Infosys vs Wipro deal wins", "comparison", ["INFY", "WIPRO"]),
    ("How did HDFC Bank and ICICI Bank do on deposits?", "comparison", ["HDFCBANK", "ICICIBANK"]),
    ("Is HUL better than ITC on volume growth?", "comparison", ["HINDUNILVR", "ITC"]),
    ("Any signs of distress or default risk at Axis Bank?", "risk", ["AXISBANK"]),
    ("Which company had the strongest margin guidance this quarter?", "single", []),
    ("What's the weather in Mumbai tomorrow?", "out_of_scope", []),
    ("Write me a poem about cats", "out_of_scope", []),
])
def test_kind_and_companies(q, kind, companies):
    got = r(q)
    assert (got.kind, got.companies) == (kind, companies)


def test_longest_alias_wins_and_no_double_count():
    assert r("What did HDFC Bank say?").companies == ["HDFCBANK"]
    assert r("Nestlé India and Nestle results").companies == ["NESTLEIND"]


def test_aliases_need_word_boundaries():
    assert r("Has the switch to cloud helped margins?").companies == []  # "itc" inside "switch"
    assert r("HCLTech guidance").companies == ["HCLTECH"]


@pytest.mark.parametrize("q, periods", [
    ("TCS Q1 FY27 margins", ["Q1 FY27"]),
    ("TCS Q1FY'27 and Q4 FY26 margins", ["Q4 FY26", "Q1 FY27"]),
    ("TCS revenue in FY26", ["Q1 FY26", "Q2 FY26", "Q3 FY26", "Q4 FY26"]),
    ("What did TCS say last quarter?", ["Q1 FY27"]),
    ("TCS and ITC over the last two quarters", ["Q3 FY26", "Q4 FY26", "Q1 FY27"]),  # each company's latest two
    ("TCS deal wins over the last 4 quarters", ["Q2 FY26", "Q3 FY26", "Q4 FY26", "Q1 FY27"]),
    ("What did TCS say about AI?", []),
])
def test_periods(q, periods):
    assert r(q).periods == periods


@pytest.mark.parametrize("q, numeric", [
    ("How much did HUL spend on A&P?", True),
    ("What was the operating margin at TCS?", True),
    ("TCS revenue growth in %", True),
    ("What did TCS say about AI partnerships?", False),
])
def test_numeric_flag(q, numeric):
    assert r(q).numeric is numeric


def test_router_disabled_sends_everything_to_single_without_filters(monkeypatch):
    monkeypatch.setenv("ROUTER_ENABLED", "false")
    got = route("Compare TCS and Infosys in Q1 FY27", COMPANIES, LATEST)
    assert (got.kind, got.companies, got.periods) == ("single", [], [])
