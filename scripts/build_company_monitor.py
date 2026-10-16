"""Build a source-linked company monitor from registered PDFs. Never call a forecast model.

Run after ingestion, before scripts/export_public_data.py. Raw PDFs stay local/ignored.
--check validates committed provenance without needing raw PDFs (suitable for CI).
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT/'backend'), str(ROOT/'scripts')]
from monitor.report import build_report, corpus_hash, period_key

import check_manifest as cm
from ingest.parse import parse_transcript

PATH = ROOT/'eval/results/company_monitor.json'


def validate(report, manifest):
    assert report['version'] == 1 and report['corpus_hash'] == corpus_hash(manifest), 'Monitor corpus is stale'
    rows = {(r['symbol'], r['fiscal_label']): r for r in manifest if r['filename']}
    assert sum(c['call_count'] for c in report['companies']) == len(rows)
    for company in report['companies']:
        trail_quotes = [q for t in company.get('follow_through', []) for q in [t['before'], t['after'], t['metric'], t['impact_source']] if q]
        for trail in company.get('follow_through', []):
            assert period_key(trail['after']['period']) - period_key(trail['before']['period']) == 1
            assert trail['verdict'] == 'Needs review'
        for fact in company['facts'] + company['commentary'] + trail_quotes:
            row = rows[company['symbol'], fact['period']]
            assert fact['source_sha256'] == row['sha256'] and fact['source_url'] == row['source_url']
            assert fact['quote'] and fact['speaker'] and fact['page'] >= 1
            if 'value' in fact:
                assert fact['raw'] in fact['quote'] and float(fact['raw'].rstrip('%')) == fact['value']


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
    validate(report, manifest)
    PATH.write_text(json.dumps(report, indent=2)+'\n')
    print('Built company monitor:', [(c['symbol'], len(c['facts']), len(c['signals'])) for c in report['companies']])


if __name__ == '__main__':
    main()
