from datetime import date

import pytest

import check_manifest as cm

PDF = b"%PDF-1.4 fake transcript"
COMPANIES = """
- {symbol: TCS, name: Tata Consultancy Services, sector: it_services, aliases: [TCS, Tata Consultancy]}
- {symbol: INFY, name: Infosys, sector: it_services, aliases: [Infosys]}
"""


@pytest.fixture
def repo(tmp_path):
    (tmp_path / "companies.yaml").write_text(COMPANIES)
    (tmp_path / "raw").mkdir()
    (tmp_path / "raw" / "TCS_Q2FY25.pdf").write_bytes(PDF)
    return tmp_path


def good_row(repo, **over):
    row = {"symbol": "TCS", "fiscal_label": "Q2 FY25", "period_end": "2024-09-30", "call_date": "2024-10-10",
           "source_url": "https://example.com/tcs.pdf", "filename": "TCS_Q2FY25.pdf",
           "sha256": cm.sha256(repo / "raw" / "TCS_Q2FY25.pdf")}
    return row | over


def run(repo, rows):
    cm.write_manifest(repo / "manifest.csv", rows)
    return cm.check(repo / "manifest.csv", repo / "companies.yaml", repo / "raw")


def test_period_end_uses_april_march_year():
    assert cm.period_end("Q1 FY26") == date(2025, 6, 30)
    assert cm.period_end("Q2 FY25") == date(2024, 9, 30)
    assert cm.period_end("Q3 FY25") == date(2024, 12, 31)
    assert cm.period_end("Q4 FY26") == date(2026, 3, 31)


def test_window_is_the_agreed_8_quarters():
    assert cm.quarters(*cm.WINDOW) == ["Q2 FY25", "Q3 FY25", "Q4 FY25", "Q1 FY26",
                                       "Q2 FY26", "Q3 FY26", "Q4 FY26", "Q1 FY27"]


@pytest.mark.parametrize("label", ["Q5 FY26", "Q1 2026", "q1 fy26", "Q1FY26", "Q1 FY'26"])
def test_bad_label_rejected(label):
    with pytest.raises(ValueError):
        cm.parse_label(label)


def test_valid_row_is_complete(repo):
    complete, pending, errors, _ = run(repo, [good_row(repo)])
    assert (complete, pending, errors) == ({("TCS", "Q2 FY25")}, [], [])


def test_row_without_filename_is_pending_not_error(repo):
    complete, pending, errors, _ = run(repo, [good_row(repo, filename="", sha256="", call_date="", source_url="")])
    assert (complete, pending, errors) == (set(), ["TCS Q2 FY25"], [])


@pytest.mark.parametrize("over, expect", [
    ({"sha256": "0" * 64}, "sha256 does not match"),
    ({"period_end": "2024-06-30"}, "should be 2024-09-30"),
    ({"fiscal_label": "Q1 FY25", "period_end": "2024-06-30", "call_date": "2024-07-15"}, "outside window"),
    ({"symbol": "RELIANCE"}, "unknown symbol"),
    ({"call_date": "2024-09-01"}, "not within 120 days"),
    ({"call_date": "2025-03-01"}, "not within 120 days"),
    ({"call_date": "10/10/2024"}, "not YYYY-MM-DD"),
    ({"source_url": ""}, "source_url"),
    ({"filename": "missing.pdf"}, "not found"),
])
def test_bad_row_is_an_error(repo, over, expect):
    complete, _, errors, _ = run(repo, [good_row(repo, **over)])
    assert complete == set()
    assert any(expect in e for e in errors), errors


def test_duplicate_quarter_and_duplicate_pdf_are_errors(repo):
    (repo / "raw" / "INFY_Q2FY25.pdf").write_bytes(PDF)  # same bytes as the TCS file
    rows = [good_row(repo), good_row(repo), good_row(repo, symbol="INFY", filename="INFY_Q2FY25.pdf")]
    _, _, errors, _ = run(repo, rows)
    assert any("duplicate symbol + fiscal_label" in e for e in errors)
    assert any("duplicate PDF" in e for e in errors)


def test_notes_list_absent_rows_and_unreferenced_pdfs(repo):
    (repo / "raw" / "stray.pdf").write_bytes(b"x")
    *_, notes = run(repo, [good_row(repo)])
    assert any("15 expected rows absent" in n for n in notes)  # 2 companies x 8 quarters - 1 present
    assert any("stray.pdf" in n for n in notes)


def test_alias_shared_by_two_companies_is_an_error(repo):
    (repo / "companies.yaml").write_text(COMPANIES + "- {symbol: X, name: X, sector: s, aliases: [tcs]}\n")
    _, errors = cm.load_companies(repo / "companies.yaml")
    assert errors == ["companies.yaml: alias 'tcs' used by both TCS and X"]


def test_init_then_fill_sha(repo):
    m = repo / "manifest.csv"
    assert cm.init(m, repo / "companies.yaml") == 16
    rows = cm.read_manifest(m)
    rows[0] |= {"call_date": "2024-10-10", "source_url": "https://example.com/t.pdf", "filename": "TCS_Q2FY25.pdf"}
    cm.write_manifest(m, rows)
    assert cm.fill_sha(m, repo / "raw") == 1
    complete, pending, errors, _ = cm.check(m, repo / "companies.yaml", repo / "raw")
    assert (len(complete), len(pending), errors) == (1, 15, [])


def test_real_companies_file_is_valid():
    companies, errors = cm.load_companies(cm.ROOT / "data/companies.yaml")
    assert errors == []
    assert len(companies) == 12
    assert {c["sector"] for c in companies.values()} == {"it_services", "private_bank", "consumer"}


THREE_SECTORS = {"A1": {"sector": "it"}, "B1": {"sector": "bank"}, "C1": {"sector": "consumer"},
                 "C2": {"sector": "consumer"}}


def all_rows(symbols, labels):
    return {(s, q) for s in symbols for q in labels}


def test_phase2_gate_needs_one_transcript_per_sector():
    g = cm.gates({("A1", "Q2 FY25"), ("B1", "Q1 FY27")}, THREE_SECTORS)
    assert g["phase2"] == (False, "sectors with a transcript: 2/3")
    g = cm.gates({("A1", "Q2 FY25"), ("B1", "Q1 FY27"), ("C2", "Q3 FY25")}, THREE_SECTORS)
    assert g["phase2"][0] is True
    assert g["A"][0] is False


def test_gate_a_is_latest_4_quarters_for_every_company():
    latest = all_rows(THREE_SECTORS, cm.quarters(*cm.TIER_A))
    assert cm.gates(latest, THREE_SECTORS)["A"] == (True, "16/16 latest-4-quarter rows complete")
    assert cm.gates(latest - {("C2", "Q1 FY27")}, THREE_SECTORS)["A"][0] is False
    assert cm.gates(latest, THREE_SECTORS)["B"][0] is False  # older 4 quarters still missing


def test_gate_b_allows_only_logged_excuses_up_to_the_cap(monkeypatch):
    full = all_rows(THREE_SECTORS, cm.quarters(*cm.WINDOW))
    assert cm.gates(full, THREE_SECTORS)["B"][0] is True
    gap = {("C2", "Q2 FY25"), ("C2", "Q3 FY25")}
    assert cm.gates(full - gap, THREE_SECTORS)["B"][0] is False  # missing and not excused
    monkeypatch.setattr(cm, "EXCUSED", {k: "not published" for k in gap})
    assert cm.gates(full - gap, THREE_SECTORS)["B"] == (True, "30/32 complete, 2 excused (max 6)")
    monkeypatch.setattr(cm, "MAX_EXCUSED", 1)
    assert cm.gates(full - gap, THREE_SECTORS)["B"][0] is False  # over the cap


def test_tier_a_is_the_last_4_quarters_of_the_window():
    assert cm.quarters(*cm.TIER_A) == cm.quarters(*cm.WINDOW)[-4:]
