import pytest
from monitor.report import company_report, margin_fact

from ingest.parse import Turn

ROW = {'symbol':'TCS','fiscal_label':'Q1 FY27','period_end':'2026-06-30',
       'source_url':'https://example.com/source.pdf','sha256':'a'*64}
COMPANY = {'symbol':'TCS','name':'Tata Consultancy Services','sector':'it_services'}


def turns(text, role='management'):
    return [Turn(speaker='CFO', role=role, section='prepared', page=3, text=text)]


def test_quarterly_value_retains_reported_change_and_exclusions():
    fact = margin_fact(turns('Our Q1 operating margin stood at 24%, down 130 bps sequentially. This excludes one-off severance.'), ROW)
    assert (fact['value'],fact['reported_change_bps']) == (24,-130)
    assert fact['basis'] == 'Excludes one-off items'
    assert fact['raw'] in fact['quote'] and 'excludes' in fact['quote']
    assert fact['page'] == 3


@pytest.mark.parametrize('text', [
    'Our operating margin guidance for the fiscal year is 20% to 22%.',
    'For FY26, our operating margin was 25%, an increase over the prior year.',
    'Our operating margin was 25%. It was the highest in four years.',
    'We expect our Q1 operating margin to reach 25%.',
    'Our Q4 operating margin stood at 25%, improving sequentially.',
    'Our Q1 operating margin stood at -10%, declining sequentially.',
    'Our Q1 operating margin stood at 120%, improving sequentially.',
])
def test_ambiguous_annual_future_wrong_period_or_invalid_values_are_not_charted(text):
    assert margin_fact(turns(text),ROW) is None


def test_conflicting_values_and_analyst_hypotheticals_are_not_charted():
    assert margin_fact(turns('Our Q1 operating margin was 24%. Our Q1 operating margin was 25%.'),ROW) is None
    assert margin_fact(turns('Our Q1 operating margin was 24%.',role='analyst'),ROW) is None


def test_wage_impact_is_not_borrowed_as_the_margin_movement():
    fact = margin_fact(turns('Operating margin for the quarter was 24%. Wage increases impacted margins by 170 bps sequentially.'),ROW)
    assert fact['reported_change_bps'] is None


def test_year_gap_never_becomes_an_independent_qoq_change():
    early = dict(ROW,fiscal_label='Q1 FY26',period_end='2025-06-30')
    c = company_report(COMPANY,[(early,turns('Our Q1 operating margin stood at 25%.')),
                              (ROW,turns('Our Q1 operating margin stood at 24%, down 130 bps sequentially.'))])
    signal = c['signals'][0]
    assert signal['previous'] is None and signal['arithmetic_matches'] is False
    assert c['gap_before'] == ['Q1 FY27']


def test_adjusted_basis_never_gets_a_comparison_crosscheck():
    early = dict(ROW,fiscal_label='Q4 FY26',period_end='2026-03-31')
    c = company_report(COMPANY,[(early,turns('Our Q4 operating margin stood at 25.3%. This excludes one-off items.')),
                              (ROW,turns('Our Q1 operating margin stood at 24%, down 130 bps sequentially.'))])
    assert c['signals'][0]['previous']
    assert c['signals'][0]['arithmetic_matches'] is False


def test_a_historical_metric_does_not_become_the_latest_signal():
    early = dict(ROW,fiscal_label='Q4 FY26',period_end='2026-03-31')
    c = company_report(COMPANY,[(early,turns('Our Q4 operating margin stood at 25.3%, up 10 bps sequentially.')),
                              (ROW,turns('No margin figure was given.'))])
    assert c['latest_period'] == 'Q1 FY27' and c['signals'] == []
