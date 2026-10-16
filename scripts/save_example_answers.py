"""Save reviewed real answers to Postgres and export a public, outage-safe snapshot.

Pass --answers with 3-4 successful answer JSON files from run_answer, --model and
--reviewed-by after checking the cited passages. --check validates the bundled file offline.
"""
import argparse
import csv
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'frontend/lib/saved-answers.json'


def validate(rows):
    if not 3 <= len(rows) <= 4:
        raise ValueError('Provide three or four reviewed real answers')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate examples')
    with (ROOT / 'data/manifest.csv').open() as f:
        registered = {(r['symbol'], r['fiscal_label']): r for r in csv.DictReader(f)}
    for row in rows:
        cited = set(map(int, re.findall(r'\[c(\d+)\]', row['answer_markdown'])))
        if not cited or cited != {s['n'] for s in row['sources']}:
            raise ValueError('Answer citations do not match the saved sources')
        datetime.fromisoformat(row['saved_at'])
        if not row['reviewed_by'] or not row['answer_markdown'] or not row['sources']:
            raise ValueError('Missing review, answer or sources')
        for source in row['sources']:
            if not source['quote'] or not source['source_url'].startswith('https://') or len(source['sha256']) != 64:
                raise ValueError('Incomplete source provenance')
            doc = registered.get((source['symbol'], source['period']), {})
            if source['sha256'] != doc.get('sha256') or source['source_url'] != doc.get('source_url'):
                raise ValueError('Saved source does not match manifest')


def save(paths, model, reviewer):
    import psycopg
    from psycopg.types.json import Jsonb

    rows = []
    with psycopg.connect(os.environ['SUPABASE_DB_URL'], connect_timeout=10,
                         options='-c search_path=quantrag,public,extensions') as conn:
        conn.execute('''create table if not exists saved_example_answers (
            id text primary key, payload jsonb not null, saved_at timestamptz not null default now())''')
        conn.execute('alter table saved_example_answers enable row level security')
        for path in paths:
            answer = json.loads(Path(path).read_text())
            if answer['refused'] or not answer['citations'] or not answer['answer_markdown']:
                raise ValueError('Examples must be successful cited answers')
            sources = []
            hits = {h['chunk_id']: h for h in answer['hits']}
            for citation in answer['citations']:
                source = conn.execute('''select c.text, c.speaker, c.page, co.symbol, d.fiscal_label,
                    d.source_url, d.sha256 from chunks c join documents d on d.id=c.document_id
                    join companies co on co.id=d.company_id where c.id=%s''', (citation['chunk_id'],)).fetchone()
                if not source or source[0] != hits[citation['chunk_id']]['text']:
                    raise ValueError('Cited passage does not match the database')
                text, speaker, page, symbol, period, url, sha = source
                if symbol != citation['symbol'] or period != citation['fiscal_label']:
                    raise ValueError('Citation company/period mismatch')
                sources.append({'n': citation['n'], 'chunk_id': citation['chunk_id'], 'quote': text,
                                    'speaker': speaker, 'page': page, 'symbol': symbol, 'period': period,
                                    'source_url': url, 'sha256': sha})
            identity = hashlib.sha256(answer['question'].encode()).hexdigest()[:16]
            payload = {'id': identity, 'question': answer['question'], 'answer_markdown': answer['answer_markdown'],
                           'model': model, 'reviewed_by': reviewer, 'sources': sources}
            saved, timestamp = conn.execute('''insert into saved_example_answers (id,payload) values (%s,%s)
                on conflict (id) do update set payload=excluded.payload, saved_at=now()
                returning payload,saved_at''', (identity, Jsonb(payload))).fetchone()
            rows.append(dict(saved, saved_at=timestamp.isoformat()))
        validate(rows)
    OUTPUT.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + '\n')
    print(f'Saved {len(rows)} reviewed answers in Postgres and exported public snapshot.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--answers', nargs='+')
    parser.add_argument('--model')
    parser.add_argument('--reviewed-by')
    args = parser.parse_args()
    if args.check:
        validate(json.loads(OUTPUT.read_text()))
        print('Saved answer snapshot has dated, reviewed source provenance.')
    elif args.answers and args.model and args.reviewed_by:
        save(args.answers, args.model, args.reviewed_by)
    else:
        parser.error('Supply --check or --answers, --model and --reviewed-by')


if __name__ == '__main__':
    main()
