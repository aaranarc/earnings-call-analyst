import copy
import csv
import json
from pathlib import Path

import pytest
from build_growth_payoff import validate
from monitor.growth import source_match

from ingest.parse import Turn


def test_reviewed_source_requires_unique_management_match():
    row = {'symbol': 'TEST', 'fiscal_label': 'Q1 FY27', 'period_end': '2026-06-30',
           'source_url': 'https://example.com/report.pdf', 'sha256': 'a'*64}
    text = 'We concluded the acquisition of 90.5% with a payout of Rs. 2,706 crores. More follows.'
    turn = Turn(speaker='CFO', role='management', section='prepared', page=2, text=text, pages=[(0, 2)])
    fact = source_match([turn], row, 'payout of Rs. 2,706')
    assert '90.5%' in fact['quote'] and '2,706 crores' in fact['quote']
    assert fact['page'] == 2 and fact['source_sha256'] == row['sha256']
    with pytest.raises(ValueError):
        source_match([turn, turn], row, 'payout of Rs. 2,706')
    turn.role = 'analyst'
    with pytest.raises(ValueError):
        source_match([turn], row, 'payout of Rs. 2,706')


def test_growth_snapshot_retains_source_and_planned_vs_actual():
    root = Path(__file__).resolve().parents[2]
    report = json.loads((root/'frontend/lib/growth-data.json').read_text())
    rows = list(csv.DictReader((root/'data/manifest.csv').open()))
    validate(report, rows)
    projects = {p['id']: p for p in report['projects']}
    assert projects['hul-minimalist']['amount'] == 2706  # Payout, not the earlier 2955 enterprise value.
    assert projects['hul-premium']['amount_label'] == 'Planned capex'
    assert projects['hcl-ai']['amount_label'] == 'Planned ceiling · up to'
    assert projects['wipro-harman']['amount'] is None
    assert all(p['payoff_status'] == 'Not established' for p in projects.values())
    bad = copy.deepcopy(report)
    bad['projects'][0]['amount_source']['source_url'] = 'https://example.com/wrong.pdf'
    with pytest.raises(AssertionError):
        validate(bad, rows)
