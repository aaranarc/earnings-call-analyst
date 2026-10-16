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

from monitor.results import percent_series_fact, quarterly_results

MARGIN = re.compile(r"\b(?:our\s+)?(?:Q[1-4]\s+)?operating margins?\b([^.!?%]{0,100}?)"
                    r"(?P<value>-?\d+(?:\.\d+)?)(?P<spacing>\s*)%", re.IGNORECASE)
GUIDANCE = re.compile(r"guidance|target|ambition|expect|outlook|aim|range", re.IGNORECASE)
ANNUAL = re.compile(r"(?:for\s+FY\s*\d{2,4}|for the year|full.year|fiscal year)", re.IGNORECASE)
QUARTER = re.compile(r"\bQ[1-4]\b|\bquarter\b|sequential|\bQoQ\b", re.IGNORECASE)
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
            left, quote = excerpt(turn.text, match.start(), match.end())
            nearby = turn.text[left:match.end()]  # Bind guidance/period checks to this sentence, not the previous one.
            sentences = re.split(r'(?<=[.!?])\s+(?=[A-Z])', quote)
            # Retain a following accounting exclusion, not an unrelated business update.
            if len(sentences) > 1 and not re.search(r'exclud|one.off|severance', sentences[1], re.IGNORECASE):
                quote = sentences[0]
            bridge = match.group(1)
            if re.match(r'\s*(?:expansion|contraction|improvement|decline|increase|decrease)\b', bridge, re.IGNORECASE):
                continue  # "Operating margin expansion to 0.9%" describes a change, not a margin level.
            if re.search(r'(?:increas|decreas|declin|expand|improv|contract)\w*\s+by\s*$', bridge, re.IGNORECASE):
                continue  # "Margins declined by 0.3% to 20.9%": 0.3% is a change, not the level.
            context = turn.text[max(0, left-300):left]
            in_quarter = QUARTER.search(nearby + quote) or (QUARTER.search(context) and not ANNUAL.search(context))
            if GUIDANCE.search(nearby) or ANNUAL.search(nearby) or not in_quarter:
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
    for candidate in candidates:
        candidate['basis'] = ('Excludes one-off items' if re.search(r'exclud.{0,50}(?:one.off|severance)', candidate['quote'], re.IGNORECASE)
                              else 'Adjusted as stated' if re.search(r'\badjusted\s+operating', candidate['quote'], re.IGNORECASE) else 'As stated in call')
    if candidates and len({x['value'] for x in candidates}) > 1:
        candidates = [c for c in candidates if c['basis'] == 'As stated in call']
    if not candidates or len({x['value'] for x in candidates}) != 1:
        return None  # Ambiguous figures require review, not a guessed choice.
    # Prefer the excerpt retaining explicit exclusions and the reported quarterly movement.
    candidates.sort(key=lambda c: (bool(re.search(r'exclud|one.off', c['quote'], re.IGNORECASE)),
                                   bool(MOVE.search(c['quote']))), reverse=True)
    fact = candidates[0]
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


def wage_statement(turns, row, kind):
    """A deliberately narrow topic match, never a promise-fulfilment verdict."""
    for turn in turns:
        if turn.role != 'management' or turn.section != 'prepared':
            continue
        boundaries = [0, *[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])', turn.text)], len(turn.text)]
        for left, right in pairwise(boundaries):
            quote = re.sub(r'\s+\d+\.$', '', turn.text[left:right].strip())
            if not re.search(r'wage (?:hike|increase)|salary increments', quote, re.IGNORECASE):
                continue
            if re.search(r'\b(?:not|never|cancel\w*|defer\w*|might|could)\b', quote, re.IGNORECASE):
                continue
            quarters = re.findall(r'\bQ([1-4])\b', quote, re.IGNORECASE)
            if quarters and quarters[-1] != row['fiscal_label'][1]:
                continue
            announcement = re.search(r'announc\w*', quote, re.IGNORECASE) and re.search(r'effective|effect from', quote, re.IGNORECASE)
            outcome = re.search(r'completed.{0,50}salary increments|wage increases announced last quarter', quote, re.IGNORECASE)
            if kind == 'outcome' and re.search(r'\b(?:will|expect\w*|would|plan\w*)\b', quote, re.IGNORECASE):
                continue
            if (kind == 'announcement' and announcement) or (kind == 'outcome' and outcome):
                return {'period': row['fiscal_label'], 'quote': quote, 'speaker': turn.speaker,
                        'page': turn.page_at(left), 'source_url': row['source_url'], 'source_sha256': row['sha256']}
    return None


def follow_through(records, facts):
    trails = []
    for (before, early_turns), (after, later_turns) in pairwise(records):
        if period_key(after['fiscal_label']) - period_key(before['fiscal_label']) != 1:
            continue
        announced = wage_statement(early_turns, before, 'announcement')
        reported = wage_statement(later_turns, after, 'outcome')
        if not announced or not reported:
            continue
        explicit = bool(re.search(r'announced last quarter', reported['quote'], re.IGNORECASE))
        metric = next((f for f in facts if f['period'] == after['fiscal_label']), None)
        impact = metric if metric and re.search(r'wage|salary', metric['quote'], re.IGNORECASE) else None
        wage_bps = re.search(r'negative impact of (\d+) basis points', reported['quote'], re.IGNORECASE)
        trails.append({'id': hashlib.sha256((before['sha256'] + after['sha256'] + announced['quote'] + reported['quote']).encode()).hexdigest()[:16],
                       'topic': 'Salary increases', 'before': announced, 'after': reported, 'metric': metric,
                       'impact_source': impact, 'wage_impact_bps': -int(wage_bps[1]) if wage_bps else None,
                       'link_basis': 'Explicit previous-quarter reference' if explicit else 'Same topic in adjacent calls; review required',
                       'outcome_label': 'Impact reported' if explicit else 'Completion reported',
                       'verdict': 'Needs review'})
    return trails


def movement_signals(facts, latest_label):
    latest = next((f for f in facts if f['period'] == latest_label), None)
    signals = []
    prior = next((f for f in facts if latest_label and period_key(f['period']) == period_key(latest_label)-1), None)
    reported = latest['reported_change_bps'] if latest else None
    derived = bool(latest and prior and latest['basis'] == prior['basis'] and latest['basis'] not in ['Excludes one-off items', 'Adjusted as stated'])
    if latest and (reported is not None or derived):
        delta = reported if reported is not None else float((Decimal(str(latest['value'])) - Decimal(str(prior['value']))) * 100)
        direction = 'down' if delta < 0 else 'up' if delta > 0 else 'unchanged'
        signals.append({'id': latest['id'] + '-movement', 'kind': 'reported_movement' if reported is not None else 'observed_change',
                        'direction': direction, 'title': f"Margin {direction}" if delta else 'Margin unchanged',
                        'change_bps': delta, 'period': latest_label, 'current': latest, 'previous': prior,
                        'attribution': 'Management-reported quarter-on-quarter change' if reported is not None else 'Calculated from as-reported figures; review comparability',
                        'arithmetic_matches': bool(prior and prior['basis'] == latest['basis'] and prior['basis'] not in ['Excludes one-off items', 'Adjusted as stated']
                            and abs((latest['value']-prior['value'])*100-delta) < .01)})
    return signals


def company_report(company, rows_and_turns):
    records = sorted(rows_and_turns, key=lambda x: period_key(x[0]['fiscal_label']))
    extractor = margin_fact if company['sector'] == 'it_services' else lambda turns, row: percent_series_fact(turns, row, company['sector'])
    facts = [f for row, turns in records if (f := extractor(turns, row))]
    comments = [c for row, turns in records if (c := commentary(turns, row))]
    latest_label = records[-1][0]['fiscal_label'] if records else None
    signals = movement_signals(facts, latest_label)
    gaps = [b['fiscal_label'] for (a, _), (b, _) in pairwise(records)
            if period_key(b['fiscal_label'])-period_key(a['fiscal_label']) != 1]
    return {'symbol': company['symbol'], 'name': company['name'], 'sector': company['sector'],
            'market': 'India', 'call_count': len(records), 'latest_period': latest_label,
            'facts': facts, 'commentary': comments, 'signals': signals, 'gap_before': gaps,
            'follow_through': follow_through(records, facts), 'result_periods': quarterly_results(company, records),
            'metric_label': {'consumer': 'EBITDA margin', 'private_bank': 'Net interest margin'}.get(company['sector'], 'Operating margin')}


def build_report(companies, manifest, load_turns, as_of=None):
    reports = []
    for company in companies:
        rows = [r for r in manifest if r['symbol'] == company['symbol'] and r['filename']]
        if rows:
            reports.append(company_report(company, [(r, load_turns(r)) for r in rows]))
    return {'version': 1, 'as_of': as_of or date.today().isoformat(), 'corpus_hash': corpus_hash(manifest),
            'method': 'Source-matched quarterly figures; company-reported and calculated movements are distinct. No semantic or causal verification.',
            'update_policy': 'Snapshot rebuilt after transcript ingestion; no continuous monitoring or price feed.',
            'companies': reports}
