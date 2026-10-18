"""Literal quarterly highlights from management remarks, with no inferred missing values."""
import hashlib
import re
from itertools import pairwise

PERCENT = re.compile(r'(?P<value>\d+(?:\.\d+)?)\s*%')
ANNUAL = re.compile(r'full.year|financial year performance|for the year|year.to.date|nine.month|first half|second half|\bH[12]\b|\bFY\s*\d{2,4}\s+(?:NIM|net interest margin)', re.IGNORECASE)
QUARTER_SCOPE = re.compile(r'quarter(?:ly)? performance|for (?:the |this )?quarter|\bQ[1-4](?:\s*FY\s*\d{2,4})?\b', re.IGNORECASE)
FUTURE = re.compile(r'\b(?:expect\w*|guidance|target\w*|would|will|could|aim)\b', re.IGNORECASE)


def statements(turns):
    for turn in turns:
        if turn.role != 'management' or turn.section != 'prepared':
            continue
        annual = False
        edges = [0, *[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])', turn.text)], len(turn.text)]
        for left, right in pairwise(edges):
            quote = re.sub(r'\s+\d+\.$', '', turn.text[left:right].strip())
            if ANNUAL.search(quote):
                annual = True
            elif QUARTER_SCOPE.search(quote):
                annual = False
            yield turn, left, quote, annual


def percent_series_fact(turns, row, sector):
    label, pattern = ('EBITDA margin', r'\bEBITDA margins?\b') if sector == 'consumer' else ('Net interest margin', r'\b(?:net interest margins?|NIMs?)\b')
    candidates = []
    for turn, left, quote, annual in statements(turns):
        match = re.search(pattern, quote, re.IGNORECASE)
        if not match or annual:
            continue
        prefix = quote[:match.start()].lower()
        if re.search(r'exclud|adjust|subsidiar|\bdomestic\b|\boverseas\b', prefix):
            continue
        after = quote[match.end():]
        value = PERCENT.search(after)
        if not value or value.start() > 65 or FUTURE.search(after[:value.start()]):
            continue
        bridge = re.sub(r'\bQ[1-4]\s*FY\s*\d{2,4}\b', '', after[:value.start()], flags=re.IGNORECASE)
        if re.search(r'\bFY\s*\d{2,4}\b', bridge, re.IGNORECASE):
            continue  # "NIM for FY26" is annual; "NIM for Q2FY26" is quarterly.
        if re.search(r'\b(?:not|never|between|range)\b', after[:value.start()]) or after[:value.start()].rstrip().endswith('-'):
            continue
        if re.search(r'\b(?:by|drop|decline|increase|expansion|contraction|impact)\b', after[:value.start()], re.IGNORECASE):
            continue  # Changes expressed as percentages are not a margin level.
        if re.match(r'\s*(?:to|and|[-–])\s*\d', after[value.end():]):
            continue
        if re.search(r'\b(?:expect|guidance|target|would|will|could)\b', prefix):
            continue
        amount = float(value['value'])
        if not 0 <= amount <= 100:
            continue
        raw = value.group()
        bases = re.findall(r'\b(consolidated|standalone)\b', turn.text[:left + match.start()], re.IGNORECASE)
        basis = bases[-1].capitalize() if sector == 'consumer' and bases else 'As stated in call'
        # A previous quarter mentioned AFTER the current value is a comparison, not its period.
        attribution = quote[:match.end() + value.start()]
        period = re.search(r'\bQ([1-4])(?:\s*FY\s*(\d{2,4}))?\b', attribution, re.IGNORECASE)
        if period and (period[1] != row['fiscal_label'][1]
                       or (period[2] and period[2][-2:] != row['fiscal_label'][-2:])):
            continue
        # Restrict the quote before comparisons so its first number remains the current result.
        candidates.append({'value': amount, 'raw': raw, 'quote': quote, 'speaker': turn.speaker,
                           'role': turn.role, 'page': turn.page_at(left), 'source_url': row['source_url'],
                           'source_sha256': row['sha256'], 'period': row['fiscal_label'], 'period_end': row['period_end'],
                           'basis': basis, 'metric_label': label, 'reported_change_bps': None})
    if not candidates:
        return None
    if sector == 'consumer':
        preferred = next((basis for basis in ['Consolidated', 'Standalone', 'As stated in call'] if any(c['basis'] == basis for c in candidates)), None)
        candidates = [c for c in candidates if c['basis'] == preferred]
    # Prefer the first explicit quarterly statement; annual scope is tracked across sentences.
    first = candidates[0]
    if len({c['value'] for c in candidates}) > 1:
        return None  # A basis dispute needs source review rather than automatic selection.
    first['id'] = hashlib.sha256((row['sha256'] + first['quote']).encode()).hexdigest()[:16]
    return first


def quarterly_results(company, records):
    """Every registered call stays selectable even if a metric requires manual review."""
    return [{'period': r['fiscal_label'], 'period_end': r['period_end'], 'call_date': r.get('call_date'),
             'source_url': r['source_url'], 'source_sha256': r['sha256'], 'reported_range': reported_range(turns, r)}
            for r, turns in records]


def reported_range(turns, row):
    for turn, left, quote, annual in statements(turns):
        if annual:
            continue
        match = re.search(r'EBITDA margins?[^.!?]{0,50}range of (?P<low>\d+(?:\.\d+)?%) to (?P<high>\d+(?:\.\d+)?%)', quote, re.IGNORECASE)
        if match and not FUTURE.search(quote[:match.end()]):
            low, high = float(match['low'].rstrip('%')), float(match['high'].rstrip('%'))
            if 0 <= low <= high <= 100:
                return {'raw': match['low'] + ' to ' + match['high'], 'lower': low, 'upper': high,
                        'raw_lower': match['low'], 'raw_upper': match['high'], 'quote': quote,
                        'speaker': turn.speaker, 'page': turn.page_at(left), 'period': row['fiscal_label'],
                        'source_url': row['source_url'], 'source_sha256': row['sha256']}
    return None


def release_margin(row, pages):
    """Keep the denominator explicit; never substitute the interest-earning-assets figure."""
    for page, text in enumerate(pages, start=1):
        text = ' '.join(text.split())
        match = re.search(r'Net interest margin was at (?P<raw>\d+(?:\.\d+)?%) on total assets(?:, and \d+(?:\.\d+)?% based on interest earning assets)?\.', text, re.IGNORECASE)
        if match:
            raw = match['raw']
            if not 0 <= float(raw.rstrip('%')) <= 100:
                return None
            return {'id': hashlib.sha256((row['sha256'] + match.group()).encode()).hexdigest()[:16],
                    'value': float(raw.rstrip('%')), 'raw': raw, 'quote': match.group(),
                    'speaker': 'HDFC Bank earnings release', 'role': 'issuer', 'page': page,
                    'source_url': row['source_url'], 'source_sha256': row['sha256'],
                    'period': row['fiscal_label'], 'period_end': row['period_end'],
                    'basis': 'On total assets', 'metric_label': 'Net interest margin',
                    'source_type': 'earnings_release', 'reported_change_bps': None}
    return None
