"""Small, JSON-exportable research notes; no shared server file or user accounts."""
import json
import math
from datetime import UTC, datetime
from uuid import uuid4


def note(title, text, sources=None):
    return {'id': str(uuid4()), 'title': title, 'text': text, 'sources': sources or [],
            'assessment': 'Unresolved', 'saved_at': datetime.now(UTC).isoformat()}


def read_notes(content):
    if len(content) > 2_000_000:
        raise ValueError('Use an export smaller than 2 MB.')
    rows = json.loads(content)
    if not isinstance(rows, list) or len(rows) > 500:
        raise ValueError('Import a JSON list with at most 500 notes.')
    for row in rows:
        if not isinstance(row, dict) or any(not isinstance(row.get(k), str) for k in ['id', 'title', 'text', 'saved_at']):
            raise ValueError('Use a Streamlit research export with id, title, text and saved_at fields.')
        if row.get('assessment') not in ['Supporting', 'Challenging', 'Unresolved']:
            raise ValueError('Unknown assessment.')
        if not isinstance(row.get('sources'), list) or any(not isinstance(s, dict) for s in row['sources']):
            raise ValueError('Sources must be a list of objects.')
    if len({r['id'] for r in rows}) != len(rows):
        raise ValueError('Duplicate note IDs.')
    return rows


def project_payoff(capital, annual_return, ramp_years, start_year, years):
    """Same linear-ramp sensitivity arithmetic as the former UI; not a prediction."""
    if (years not in (3, 5) or not all(math.isfinite(v) for v in (capital, annual_return))
            or not 0 < capital <= 1e7 or not -20 <= annual_return <= 50
            or ramp_years not in range(1, 6) or start_year not in range(1, 6)):
        raise ValueError('Invalid scenario assumptions.')
    return [{'Year': year, 'Annual incremental operating profit (₹ crore)':
             capital * annual_return / 100 * min(1, max(0, (year - start_year + 1) / ramp_years))}
            for year in range(years + 1)]
