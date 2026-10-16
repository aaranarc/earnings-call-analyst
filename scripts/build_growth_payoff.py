"""Build source-linked project timelines; --check verifies the committed snapshot."""
import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'backend'))
from monitor.growth import PROJECTS, build_growth

from ingest.parse import parse_transcript

OUTPUT = ROOT/'frontend/lib/growth-data.json'


def validate(report, rows):
    known = {(r['symbol'], r['fiscal_label'], r['sha256']): r for r in rows if r['filename']}
    assert report['version'] == 1
    specs = {p['id']: p for p in PROJECTS}
    assert {p['id'] for p in report['projects']} == set(specs)
    for p in report['projects']:
        spec = specs[p['id']]
        for key in ('symbol', 'name', 'amount', 'amount_label', 'outcome', 'missing'):
            assert p[key] == spec[key], f'Reviewed project definition differs: {key}'
        assert len(p['milestones']) == len(spec['milestones'])
        for q, (period, stage, label, needle, value) in zip(p['milestones'], spec['milestones'], strict=True):
            assert (q['period'], q['stage'], q['label'], q['value_text']) == (period, stage, label, value)
            assert needle.lower() in q['quote'].lower()
        assert p['payoff_status'] == 'Not established'
        for q in p['milestones'] + ([p['amount_source']] if p['amount_source'] else []):
            r = known[p['symbol'], q['period'], q['source_sha256']]
            assert q['source_url'] == r['source_url'] and q['period_end'] == r['period_end']
            assert q['page'] >= 1 and q['quote'] and q['speaker']
        if p['amount'] is not None:
            assert f"{p['amount']:,}" in p['amount_source']['quote']
        metric = p.get('operating_metric')
        if metric:
            assert metric['source'] in p['milestones']
            assert f"{metric['before']:,}" in metric['source']['quote']
            assert f"{metric['after']:,}-plus" in metric['source']['quote']
            assert metric['after_is_lower_bound']
    hashes = sorted({q['source_sha256'] for p in report['projects'] for q in p['milestones']})
    assert report['source_hash'] == hashlib.sha256(''.join(hashes).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    rows = list(csv.DictReader((ROOT/'data/manifest.csv').open()))
    if args.check:
        validate(json.loads(OUTPUT.read_text()), rows)
        print('Growth Payoff provenance matches the registered corpus.')
        return

    def load(row):
        path = ROOT/'data/raw'/row['filename']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == row['sha256']
        return parse_transcript(path)

    as_of = json.loads((ROOT/'eval/results/ingest_stats.json').read_text())['date']
    report = build_growth(rows, load, as_of)
    validate(report, rows)
    OUTPUT.write_text(json.dumps(report, indent=2)+'\n')
    print('Built', len(report['projects']), 'reviewed project timelines.')


if __name__ == '__main__':
    main()
