from pathlib import Path

import pytest

import check_manifest as cm
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
    ("Which company had the strongest margin guidance this quarter?", "comparison", []),
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


@pytest.mark.parametrize("wording", ["this quarter", "latest quarter", "most recent quarter"])
def test_latest_wording_uses_ingested_period_not_today(wording):
    got = route(f"Infosys margins {wording}", COMPANIES, {"INFY": "Q2 FY25"}, enabled=True)
    assert got.periods == ["Q2 FY25"]
    assert "not the calendar quarter" in got.reason


@pytest.mark.parametrize("question, periods", [
    ("TCS Q4 FY26 margins reported this quarter", ["Q4 FY26"]),
    ("TCS FY26 revenue, latest quarter commentary", ["Q1 FY26", "Q2 FY26", "Q3 FY26", "Q4 FY26"]),
    ("TCS Q4 FY26 margins last quarter", ["Q4 FY26"]),
])
def test_explicit_periods_take_precedence(question, periods):
    assert r(question).periods == periods


@pytest.mark.parametrize("question, sector", [
    ("Which bank had the best CASA ratio?", "private_bank"),
    ("Compare banks on deposit growth", "private_bank"),
    ("How is the banking sector doing on credit risk?", "private_bank"),
    ("How is the IT services sector doing on pricing?", "it_services"),
    ("Which IT company has the highest margin?", "it_services"),
    ("Compare IT companies on revenue", "it_services"),
    ("Compare FMCG demand", "consumer"),
    ("Consumer goods revenue outlook", "consumer"),
])
def test_sector_questions_stay_inside_sector(question, sector):
    got = r(question)
    assert got.companies == [s for s, c in COMPANIES.items() if c["sector"] == sector]
    assert got.kind == ("risk" if "risk" in question else "comparison")


def test_explicit_company_not_expanded_by_sector_word():
    assert r("HDFC Bank versus the banking sector on deposits").companies == ["HDFCBANK"]
    assert r("How is TCS doing in IT services pricing?").companies == ["TCS"]


def test_incidental_it_or_consumer_word_does_not_select_sector():
    assert r("Is it a good quarter for consumer demand?").companies == []


def test_router_ablation_also_disables_sector_and_latest_filters():
    got = route("Which bank did best this quarter?", COMPANIES, LATEST, enabled=False)
    assert (got.kind, got.companies, got.periods) == ("single", [], [])
