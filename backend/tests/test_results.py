import pytest
from monitor.results import percent_series_fact, release_margin, reported_range

from ingest.parse import Turn

ROW = {'symbol':'HINDUNILVR', 'fiscal_label':'Q2 FY26', 'period_end':'2025-09-30',
       'source_url':'https://example.com/results.pdf', 'sha256':'a'*64}


def remarks(text):
    return [Turn(speaker='CFO', role='management', section='prepared', page=5, text=text)]


def test_quarterly_consumer_margin_does_not_borrow_half_year_or_standalone_result():
    source = remarks('Our consolidated performance for the quarter was strong. EBITDA margin was 23.2%. Coming to our performance for the first half of financial year 2026. EBITDA margin was 23%.')
    fact = percent_series_fact(source, ROW, 'consumer')
    assert fact['raw'] == '23.2%' and fact['basis'] == 'Consolidated'
    source = remarks('Our consolidated results for the quarter were strong. EBITDA margin was 22.8%. Our standalone performance for the quarter reflects growth. EBITDA margin stood at 22.6%.')
    assert percent_series_fact(source, ROW, 'consumer')['raw'] == '22.8%'


def test_bank_margin_keeps_current_value_separate_from_comparator_and_adjustment():
    source = remarks('The net interest margin was 4.36% in this quarter compared to 4.32% previously. Excluding tax refund, the net interest margin would have been 4.28%.')
    assert percent_series_fact(source, ROW, 'private_bank')['raw'] == '4.36%'


@pytest.mark.parametrize('text', ['EBITDA margin is not 24%.', 'We expect EBITDA margin to reach 24%.', 'EBITDA margin was between 20% and 24%.', 'EBITDA margin was -5%.'])
def test_uncertain_or_nonliteral_levels_are_not_charted(text):
    assert percent_series_fact(remarks(text), ROW, 'consumer') is None


def test_financial_release_preserves_both_denominators_but_charts_total_assets_only():
    fact = release_margin(ROW, ['Net interest margin was at 3.26% on total assets, and 3.40% based on interest earning assets.'])
    assert fact['raw'] == '3.26%' and fact['basis'] == 'On total assets'
    assert '3.40%' in fact['quote'] and fact['source_type'] == 'earnings_release'
    assert fact['reported_change_bps'] is None


def test_reported_range_is_preserved_without_inventing_a_midpoint():
    source = remarks('EBITDA margin was maintained within the healthy range of 23% to 24%.')
    assert percent_series_fact(source, ROW, 'consumer') is None
    value = reported_range(source, ROW)
    assert (value['lower'],value['upper']) == (23,24) and 'value' not in value
    assert reported_range(remarks('We expect EBITDA margin in the range of 23% to 24%.'), ROW) is None


def test_bank_acronym_does_not_mix_domestic_or_annual_basis():
    source = remarks('FY26 NIM at 4.60%. For the quarter Q2FY26, domestic NIMs were 4.80%. Overall NIM stood at 4.54%, compared to 4.65% in Q1FY26.')
    fact = percent_series_fact(source, ROW, 'private_bank')
    assert fact['raw'] == '4.54%'
    assert 'compared to 4.65%' in fact['quote']


def test_current_bank_margin_is_not_rejected_by_a_previous_quarter_comparison():
    row = dict(ROW, fiscal_label='Q1 FY27')
    source = remarks('Net interest margin for the quarter 4.53%, remained consistent with Q3FY26 and adjusted Q4 margin. As you would recall, we had reported 4.67% NIM margin for Q4.')
    assert percent_series_fact(source, row, 'private_bank')['raw'] == '4.53%'


@pytest.mark.parametrize('text', [
    'FY26 NIM at 4.60%.', 'Full year NIM for FY26 was 4.60%.',
    'Domestic NIMs at 4.80%.', 'NIM declined by 0.2% to 4.54%.',
    'We expect NIM to improve to 4.8%.', 'Adjusted NIM for Q2 was 4.58%.',
    'NIM for FY26 was 4.60%.', 'NIM for Q2FY25 was 4.60%.',
])
def test_bank_acronym_does_not_turn_other_bases_or_changes_into_reported_levels(text):
    assert percent_series_fact(remarks(text), ROW, 'private_bank') is None
