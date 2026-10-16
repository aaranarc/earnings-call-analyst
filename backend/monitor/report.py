"""Extract a small, explicit metric vocabulary and publish only literal source matches.

A reported movement is management's statement, not independently established causality.
Missing periods, conflicting values and annual/guidance figures never become QoQ comparisons.
"""
import hashlib
import json
import re
from datetime import date
from decimal import Decimal
from itertools import pairwise

MARGIN = re.compile(r"\b(?:our\s+)?(?:Q[1-4]\s+)?operating margins?\b([^.!?%]{0,100}?)"
                    r"(?P<value>-?\d+(?:\.\d+)?)(?P<spacing>\s*)%", re.IGNORECASE)
GUIDANCE = re.compile(r"guidance|target|ambition|expect|outlook|aim|range", re.IGNORECASE)
ANNUAL = re.compile(r"(?:for\s+FY\s*\d{2,4}|for the year|full.year|fiscal year)", re.IGNORECASE)
QUARTER = re.compile(r"\bQ[1-4]\b|\bquarter\b|sequential", re.IGNORECASE)
MOVE = re.compile(r"\b(?P<direction>down|declin\w*|decreas\w*|up|increas\w*|improv\w*|expand\w*)"
                  r"(?:\s+of|\s+by)?\s+(?P<amount>\d+(?:\.\d+)?)\s*(?:bps|basis points)", re.IGNORECASE)


def period_key(label):
    q, fy = re.fullmatch(r"Q([1-4]) FY(\d{2})", label).groups()
    return int(fy) * 4 + int(q)


def corpus_hash(manifest):
    registered = sorted((r['symbol'], r['fiscal_label'], r['sha256']) for r in manifest if r['filename'])
    return hashlib.sha256(json.dumps(registered, separators=(',', ':')).encode()).hexdigest()


def excerpt(text, start, end):
    # Two sentences retain nearby exclusions, not only the percentage.
    before = text.rfind('. ', 0, start)
    left = before + 2 if before >= 0 else 0
    ends = [m.end() for m in re.finditer(r'[.!?](?:\s+|$)', text[end:])]
    right = end + ends[min(1, len(ends)-1)] if ends else len(text)
    return left, text[left:min(right, left + 1200)].strip()


def margin_fact(turns, row):
    candidates = []
    for turn in turns:
        if turn.role != 'management' or turn.section != 'prepared':
            continue
        for match in MARGIN.finditer(turn.text):
            nearby = turn.text[max(0, match.start()-70):match.end()]
            left, quote = excerpt(turn.text, match.start(), match.end())
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', quote)
            # Retain a following accounting exclusion, not an unrelated business update.
            if len(sentences) > 1 and not re.search(r'exclud|one.off|severance', sentences[1], re.IGNORECASE):
                quote = sentences[0]
            bridge = match.group(1)
            if GUIDANCE.search(nearby) or ANNUAL.search(nearby) or not QUARTER.search(nearby + quote):
                continue
            # A percentage attributed to another named quarter is not this document's quarter.
            quarters = re.findall(r'\bQ([1-4])\b', nearby, re.IGNORECASE)
            if quarters and quarters[-1] != row['fiscal_label'][1]:
                continue
            raw = match.group('value')
            if not (Decimal(0) <= Decimal(raw) <= Decimal(100)) or GUIDANCE.search(bridge):
                continue
            page = turn.page_at(left)
            candidates.append({'value': float(raw), 'raw': raw + match.group('spacing') + '%', 'quote': quote,
                               'speaker': turn.speaker, 'role': turn.role, 'page': page,
                               'source_url': row['source_url'], 'source_sha256': row['sha256'],
                               'period': row['fiscal_label'], 'period_end': row['period_end']})
    if not candidates or len({x['value'] for x in candidates}) != 1:
        return None  # Ambiguous figures require review, not a guessed choice.
    # Prefer the excerpt retaining explicit exclusions and the reported quarterly movement.
    candidates.sort(key=lambda c: (bool(re.search(r'exclud|one.off', c['quote'], re.IGNORECASE)),
                                   bool(MOVE.search(c['quote']))), reverse=True)
    fact = candidates[0]
    fact['basis'] = 'Excludes one-off items' if re.search(r'exclud.{0,50}(?:one.off|severance)', fact['quote'], re.IGNORECASE) else 'As stated in call'
    fact['id'] = hashlib.sha256((row['sha256'] + fact['quote']).encode()).hexdigest()[:16]
    # Only movements in the metric's first sentence; do not borrow a currency/wage impact later on.
    first = re.split(r'(?<=[.!?])\s+(?=[A-Z])', fact['quote'])[0]
    move = MOVE.search(first)
    fact['reported_change_bps'] = None
    if move and re.search(r'sequential|QoQ|quarter.on.quarter', first, re.IGNORECASE):
        amount = float(move['amount'])
        fact['reported_change_bps'] = -amount if re.match(r'down|declin|decreas', move['direction'], re.IGNORECASE) else amount
    return fact


def commentary(turns, row):
    # Quotes provide management's explanation, not an automatically proven cause.
    for turn in turns:
        if turn.role != 'management' or turn.section != 'prepared':
            continue
        for m in re.finditer(r'wage|salary|increments|compensation', turn.text, re.IGNORECASE):
            left, quote = excerpt(turn.text, m.start(), m.end())
            if re.search(r'margin|basis points|\bbps\b', quote, re.IGNORECASE):
                return {'period': row['fiscal_label'], 'quote': quote, 'speaker': turn.speaker,
                        'page': turn.page_at(left), 'source_url': row['source_url'], 'source_sha256': row['sha256']}
    return None


def company_report(company, rows_and_turns):
    records = sorted(rows_and_turns, key=lambda x: period_key(x[0]['fiscal_label']))
    facts = [f for row, turns in records if (f := margin_fact(turns, row))]
    comments = [c for row, turns in records if (c := commentary(turns, row))]
    latest_label = records[-1][0]['fiscal_label'] if records else None
    latest = next((f for f in facts if f['period'] == latest_label), None)
    signals = []
    if latest and latest['reported_change_bps'] is not None:
        delta = latest['reported_change_bps']
        direction = 'down' if delta < 0 else 'up' if delta > 0 else 'unchanged'
        prior = next((f for f in facts if period_key(f['period']) == period_key(latest_label)-1), None)
        signals.append({'id': latest['id'] + '-movement', 'kind': 'reported_movement',
                        'direction': direction, 'title': f"Margin {direction}" if delta else 'Margin unchanged',
                        'change_bps': delta, 'period': latest_label, 'current': latest, 'previous': prior,
                        'attribution': 'Management-reported quarter-on-quarter change',
                        'arithmetic_matches': bool(prior and prior['basis'] == latest['basis'] == 'As stated in call'
                            and abs((latest['value']-prior['value'])*100-delta) < .01)})
    gaps = [b['period'] for a, b in pairwise(facts) if period_key(b['period'])-period_key(a['period']) != 1]
    return {'symbol': company['symbol'], 'name': company['name'], 'sector': company['sector'],
            'market': 'India', 'call_count': len(records), 'latest_period': latest_label,
            'facts': facts, 'commentary': comments, 'signals': signals, 'gap_before': gaps}


def build_report(companies, manifest, load_turns, as_of=None):
    reports = []
    for company in companies:
        rows = [r for r in manifest if r['symbol'] == company['symbol'] and r['filename']]
        if rows:
            reports.append(company_report(company, [(r, load_turns(r)) for r in rows]))
    return {'version': 1, 'as_of': as_of or date.today().isoformat(), 'corpus_hash': corpus_hash(manifest),
            'method': 'Rule-based extraction from management prepared remarks; source matches are not semantic verification.',
            'update_policy': 'Snapshot rebuilt after transcript ingestion; no continuous monitoring or price feed.',
            'companies': reports}
