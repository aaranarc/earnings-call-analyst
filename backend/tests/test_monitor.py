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


def test_follow_through_keeps_announcement_completion_and_attributed_movement_separate():
    early = dict(ROW, fiscal_label='Q4 FY26', period_end='2026-03-31')
    c = company_report(COMPANY, [(early, turns('We have announced annual salary increments, effective April 1.')),
                              (ROW, turns('This quarter, we completed annual salary increments globally. Our Q1 operating margins stood at 24%, down 130 bps sequentially, primarily due to wage hikes.'))])
    trail = c['follow_through'][0]
    assert trail['before']['period'] == 'Q4 FY26' and trail['after']['period'] == 'Q1 FY27'
    assert trail['verdict'] == 'Needs review'
    assert trail['link_basis'] == 'Same topic in adjacent calls; review required'
    assert trail['wage_impact_bps'] is None  # Net movement is not a quantified wage-only impact.
    assert trail['impact_source']['reported_change_bps'] == -130


@pytest.mark.parametrize('outcome,role', [
    ('We have not completed annual salary increments.', 'management'),
    ('We expect to have completed annual salary increments next quarter.', 'management'),
    ('We completed annual salary increments.', 'analyst'),
    ('We completed annual salary increments in Q3.', 'management'),
])
def test_follow_through_rejects_negation_future_analyst_and_wrong_period(outcome, role):
    early = dict(ROW, fiscal_label='Q4 FY26')
    c = company_report(COMPANY, [(early, turns('We announced salary increments, effective April 1.')),
                               (ROW, turns(outcome, role=role))])
    assert c['follow_through'] == []


def test_follow_through_requires_adjacent_calls_and_never_borrows_another_cost_impact():
    early = dict(ROW, fiscal_label='Q2 FY26')
    later = dict(ROW, fiscal_label='Q3 FY26')
    announcement = turns('We announced a wage hike with effect from September 1st.')
    outcome = turns('Full quarter impact of the wage increases announced last quarter had a negative impact of 50 basis points. Partnerships had an impact of 70 basis points.')
    trail = company_report(COMPANY, [(early, announcement), (later, outcome)])['follow_through'][0]
    assert trail['wage_impact_bps'] == -50 and trail['metric'] is None
    assert trail['link_basis'] == 'Explicit previous-quarter reference'
    assert 'Partnerships' not in trail['after']['quote']
    assert company_report(COMPANY, [(early, announcement), (ROW, outcome)])['follow_through'] == []


def test_adjacent_reported_levels_get_a_labeled_calculation_not_a_management_claim():
    early = dict(ROW, fiscal_label='Q4 FY26')
    report = company_report(COMPANY, [(early, turns('Our Q4 operating margin was 17.3%.')),
                                    (ROW, turns('Our Q1 operating margin was 16%.'))])
    signal = report['signals'][0]
    assert signal['kind'] == 'observed_change' and signal['change_bps'] == -130
    assert 'review comparability' in signal['attribution']


def test_adjusted_levels_do_not_generate_a_derived_change():
    early = dict(ROW, fiscal_label='Q4 FY26')
    report = company_report(COMPANY, [(early, turns('Our Q4 operating margin was 25%. This excludes one-off items.')),
                                    (ROW, turns('Our Q1 operating margin was 24%. This excludes one-off items.'))])
    assert report['signals'] == []


def test_margin_percentage_change_does_not_conflict_with_actual_level():
    source = turns('Our Q1 operating margin stood at 20.9%. Operating margins for Q1 declined by 0.3% to 20.9%, sequentially.')
    assert margin_fact(source, ROW)['raw'] == '20.9%'


def test_reported_and_adjusted_margins_keep_their_basis():
    source = turns('Our adjusted operating margin for the quarter was 17.2%. Our operating margins for Q1 at 16.7% contracted quarter-on-quarter.')
    fact = margin_fact(source, ROW)
    assert fact['raw'] == '16.7%' and fact['basis'] == 'As stated in call'


def test_quarter_context_can_come_from_the_preceding_performance_sentence():
    source = turns('Getting into our business performance for the quarter. Our revenue grew sequentially. Our operating margin stood at 19.5%.')
    assert margin_fact(source, ROW)['raw'] == '19.5%'


def test_margin_expansion_percentage_is_not_an_operating_margin_level():
    source = turns('For Q1, operating margins stood at 17.5%. This brings our FY27 operating margin expansion to 0.9%.')
    assert margin_fact(source, ROW)['raw'] == '17.5%'
