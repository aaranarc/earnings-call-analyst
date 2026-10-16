"""Build a source-linked company monitor from registered PDFs. Never call a forecast model.

Run after ingestion, before scripts/export_public_data.py. Raw PDFs stay local/ignored.
--check validates committed provenance without needing raw PDFs (suitable for CI).
"""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'scripts')]
from monitor.report import build_report, corpus_hash, movement_signals, period_key
from monitor.results import release_margin

import check_manifest as cm
from ingest.parse import parse_transcript, pdf_pages

PATH = ROOT/'eval/results/company_monitor.json'


def validate(report, manifest):
    assert report['version'] == 1 and report['corpus_hash'] == corpus_hash(manifest), 'Monitor corpus is stale'
    extras_path = ROOT/'data/results_manifest.csv'
    extras = list(csv.DictReader(extras_path.open())) if extras_path.exists() else []
    rows = {(r['symbol'], r['fiscal_label'], r['sha256']): r for r in manifest + extras if r['filename']}
    assert report.get('supplemental_hash') == corpus_hash(extras)
    assert sum(c['call_count'] for c in report['companies']) == sum(bool(r['filename']) for r in manifest)
    expected_periods = {(r['symbol'],r['fiscal_label']) for r in manifest if r['filename']}
    actual_periods = {(c['symbol'],p['period']) for c in report['companies'] for p in c.get('result_periods', [])}
    assert actual_periods == expected_periods, 'Every registered call must stay selectable'
    for company in report['companies']:
        trail_quotes = [q for t in company.get('follow_through', []) for q in [t['before'], t['after'], t['metric'], t['impact_source']] if q]
        range_quotes = [p['reported_range'] for p in company.get('result_periods', []) if p.get('reported_range')]
        for trail in company.get('follow_through', []):
            assert period_key(trail['after']['period']) - period_key(trail['before']['period']) == 1
            assert trail['verdict'] == 'Needs review'
        for fact in company['facts'] + company['commentary'] + trail_quotes + range_quotes:
            row = rows[company['symbol'], fact['period'], fact['source_sha256']]
            assert fact['source_sha256'] == row['sha256'] and fact['source_url'] == row['source_url']
            assert fact['quote'] and fact['speaker'] and fact['page'] >= 1
            if 'value' in fact:
                assert fact['raw'] in fact['quote'] and float(fact['raw'].rstrip('%')) == fact['value']
            if 'lower' in fact:
                assert fact['raw_lower'] in fact['quote'] and fact['raw_upper'] in fact['quote']
                assert 0 <= fact['lower'] <= fact['upper'] <= 100


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--check', action='store_true')
    args = p.parse_args()
    manifest = cm.read_manifest(ROOT/'data/manifest.csv')
    if args.check:
        validate(json.loads(PATH.read_text()), manifest)
        print('Company monitor provenance matches registered corpus.')
        return
    complete, _, errors, _ = cm.check(ROOT/'data/manifest.csv', ROOT/'data/companies.yaml', ROOT/'data/raw')
    if errors or len(complete) != sum(bool(r['filename']) for r in manifest):
        raise SystemExit('Registered PDFs must pass manifest verification before building signals.')
    companies, _ = cm.load_companies(ROOT/'data/companies.yaml')
    report = build_report(companies.values(), manifest, lambda row: parse_transcript(ROOT/'data/raw'/row['filename']),
                          as_of=json.loads((ROOT/'eval/results/ingest_stats.json').read_text())['date'])
    extras_path = ROOT/'data/results_manifest.csv'
    extras = list(csv.DictReader(extras_path.open())) if extras_path.exists() else []
    report['supplemental_hash'] = corpus_hash(extras)
    report['financial_release_count'] = len(extras)
    for row in extras:
        path = ROOT/'data/raw'/row['filename']
        if hashlib.sha256(path.read_bytes()).hexdigest() != row['sha256']:
            raise SystemExit('Financial result PDF hash mismatch')
        fact = release_margin(row, pdf_pages(path))
        if not fact:
            raise SystemExit('No unambiguous result in registered financial release')
        company = next(c for c in report['companies'] if c['symbol'] == row['symbol'])
        company['facts'] = [f for f in company['facts'] if f['period'] != fact['period']] + [fact]
        company['facts'].sort(key=lambda f: period_key(f['period']))
        company['signals'] = movement_signals(company['facts'], company['latest_period'])
    validate(report, manifest)
    PATH.write_text(json.dumps(report, indent=2)+'\n')
    print('Built company monitor:', [(c['symbol'], len(c['facts']), len(c['signals'])) for c in report['companies']])


if __name__ == '__main__':
    main()
