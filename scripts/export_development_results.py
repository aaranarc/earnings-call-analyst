"""Export recorded development measurements for the dashboard, never benchmark claims."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'eval/results/smoke_retrieval.json'
OUTPUT = ROOT / 'frontend/lib/development-results.json'


def snapshot():
    runs = json.loads(SOURCE.read_text())['runs']
    final = [r for r in runs if r['label'] == '4 final defaults (top 10)' and r['reranker_loaded']]
    rows = []
    for config in final[0]['configs']:
        values = [r['configs'][config] for r in final]
        rows.append({'name': config, 'hits_min': min(v['hits'] for v in values),
                     'hits_max': max(v['hits'] for v in values), 'of': values[0]['of'],
                     'p50_min_ms': min(v['p50_s'] for v in values) * 1000,
                     'p50_max_ms': max(v['p50_s'] for v in values) * 1000})
    retained = [r['peak_rss_mb'] for r in runs if r['reranker_loaded'] and r['settings'] ==
                {'batch_size': 4, 'max_tokens': 384, 'fuse_top': 10} and r['label'].startswith(('2b', '4 '))]
    untuned = [r['peak_rss_mb'] for r in runs if r['reranker_loaded'] and r['settings'] ==
               {'batch_size': 64, 'max_tokens': 512, 'fuse_top': 20}]
    return {'source': 'eval/results/smoke_retrieval.json', 'sha256': hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
            'machine': final[0]['machine'], 'source_commit': final[0]['git_sha'], 'runs': len(final), 'retrieval': rows,
            'memory': {'retained_min_mb': min(retained), 'retained_max_mb': max(retained),
                       'untuned_min_mb': min(untuned), 'untuned_max_mb': max(untuned), 'retained_runs': len(retained)}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    text = json.dumps(snapshot(), indent=2) + '\n'
    if args.check:
        if OUTPUT.read_text() != text:
            raise SystemExit('Development snapshot stale; run scripts/export_development_results.py')
    else:
        OUTPUT.write_text(text)


if __name__ == '__main__':
    main()
