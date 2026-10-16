"""Reviewed project vocabulary, literal management evidence, no inferred ROI.

New projects require reviewed selectors. Completion and operational growth do not
establish an investment return. Amounts retain planned/ceiling/paid distinctions.
"""
import hashlib
import re

PROJECTS = [
    {'id': 'hul-minimalist', 'symbol': 'HINDUNILVR', 'name': 'Minimalist', 'category': 'Acquisition',
         'amount': 2706, 'amount_label': 'Reported payout', 'amount_period': 'Q1 FY26', 'amount_match': '2,706',
         'outcome': 'Distribution expanded', 'missing': 'Project-level profit and cash returns are not disclosed in these excerpts.',
         'milestones': [
             ('Q3 FY25', 'Announced', 'Definitive agreement', 'definitive agreement to acquire a stake', None),
             ('Q1 FY26', 'Completed', '90.5% stake acquired', 'successfully concluded the acquisition', None),
             ('Q3 FY26', 'Operating progress', '25,000+ stores', 'expanded the brand into 25,000-plus', '25,000'),
             ('Q4 FY26', 'Trading update', 'Double-digit growth reported', 'Minimalist delivering strong double-digit', None),
         ]},
    {'id': 'hul-premium', 'symbol': 'HINDUNILVR', 'name': 'Premium-format capacity', 'category': 'Capacity expansion',
         'amount': 2000, 'amount_label': 'Planned capex', 'amount_period': 'Q4 FY26', 'amount_match': '2,000 crores planned capex investment',
         'outcome': 'Investment announced', 'missing': 'Completion date, utilisation and project returns are not available in this snapshot.',
         'milestones': [('Q4 FY26', 'Planned', '₹2,000 cr capacity plan', '2,000 crores planned capex investment', '2,000')]},
    {'id': 'hcl-ai', 'symbol': 'HCLTECH', 'name': 'AI infrastructure', 'category': 'Capacity expansion',
         'amount': 3500, 'amount_label': 'Planned ceiling · up to', 'amount_period': 'Q1 FY27', 'amount_match': 'strategic investment of up to INR3,500',
         'outcome': 'Investment announced', 'missing': '50 MW is potential capacity, not commissioned capacity. Project returns are not disclosed.',
         'milestones': [('Q1 FY27', 'Planned', 'Up to ₹3,500 cr · potential 50 MW', 'strategic investment of up to INR3,500', '3,500')]},
    {'id': 'wipro-harman', 'symbol': 'WIPRO', 'name': 'HARMAN DTS', 'category': 'Acquisition',
         'amount': None, 'amount_label': 'Payout not extracted', 'amount_period': None, 'amount_match': None,
         'outcome': 'Revenue contribution reported', 'missing': 'Revenue contribution is not profit, cash return or acquisition ROI.',
         'milestones': [
             ('Q2 FY26', 'Announced', 'Closing expected next quarter', 'Harman Digital Transformation Solutions acquisition', None),
             ('Q3 FY26', 'Completed', 'Integration underway', 'With the acquisition now complete', None),
             ('Q3 FY26', 'Contribution', '0.8% growth contribution', 'numbers included 0.8% as contribution', '0.8%'),
         ]},
]


def source_match(turns, row, needle):
    """Keep surrounding sentences, including decimal points and page provenance."""
    matches = []
    for turn in turns:
        if turn.role != 'management' or turn.section != 'prepared':
            continue
        for m in re.finditer(re.escape(needle), turn.text, re.IGNORECASE):
            # A sentence break must be punctuation followed by whitespace, not 90.5.
            ends = [x.end() for x in re.finditer(r'[.!?]\s+(?=[A-Z])', turn.text)]
            left = max((x for x in ends if x <= m.start()), default=0)
            right = next((x for x in ends if x >= m.end()), len(turn.text))
            quote = turn.text[left:right].strip()
            matches.append({'period': row['fiscal_label'], 'period_end': row['period_end'],
                                'quote': quote, 'speaker': turn.speaker, 'page': turn.page_at(left),
                                'source_url': row['source_url'], 'source_sha256': row['sha256']})
    if len(matches) != 1:
        raise ValueError(f'Expected one reviewed source match: {row["symbol"]} {needle}; got {len(matches)}')
    return matches[0]


def build_growth(manifest, load_turns, as_of):
    rows = {(r['symbol'], r['fiscal_label']): r for r in manifest if r['filename']}
    cache, projects = {}, []

    def evidence(symbol, period, needle):
        row = rows[symbol, period]
        key = (symbol, period)
        if key not in cache:
            cache[key] = load_turns(row)
        return source_match(cache[key], row, needle)

    for spec in PROJECTS:
        project = {k: v for k, v in spec.items() if k not in ('milestones', 'amount_match', 'amount_period')}
        project['milestones'] = [dict(stage=stage, label=label, value_text=value,
                                      **evidence(spec['symbol'], period, needle))
                                 for period, stage, label, needle, value in spec['milestones']]
        project['amount_source'] = (evidence(spec['symbol'], spec['amount_period'], spec['amount_match'])
                                    if spec['amount'] is not None else None)
        project['operating_metric'] = None
        if spec['id'] == 'hul-minimalist':
            source = project['milestones'][2]
            assert '25,000-plus offline stores from 3,000' in source['quote']
            project['operating_metric'] = {'label': 'Distribution reach', 'unit': 'stores',
                                           'before': 3000, 'after': 25000, 'after_is_lower_bound': True,
                                           'before_label': 'At acquisition', 'after_label': source['period'],
                                           'source': source}
        project['payoff_status'] = 'Not established'
        projects.append(project)
    fingerprints = sorted({m['source_sha256'] for p in projects for m in p['milestones']})
    return {'version': 1, 'as_of': as_of, 'source_hash': hashlib.sha256(''.join(fingerprints).encode()).hexdigest(),
                'methodology': 'Reviewed project selectors; literal management statements. No inferred return or forecast.',
                'projects': projects}
