"""Exercise the shared counter only against CI's disposable localhost database."""
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from urllib.parse import urlparse

import pytest
from quantrag.usage import BudgetExceeded, reserve

URL = os.getenv('TEST_DATABASE_URL', '')


@pytest.mark.skipif(urlparse(URL).hostname not in ('localhost', '127.0.0.1'),
                    reason='requires disposable localhost Postgres')
def test_shared_counter_is_atomic_and_rejections_do_not_consume_units(monkeypatch):
    import psycopg

    monkeypatch.setenv('SUPABASE_DB_URL', URL)
    monkeypatch.setenv('USAGE_BACKEND', 'postgres')
    monkeypatch.setenv('DAILY_REQUEST_LIMIT', '5')
    now = datetime(2026, 11, 4, tzinfo=UTC)
    with psycopg.connect(URL) as conn:
        conn.execute('drop table if exists quantrag.api_daily_usage')

    def attempt(_):
        try:
            reserve(now=now)
            return True
        except BudgetExceeded:
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(attempt, range(12))) == 5
    with pytest.raises(BudgetExceeded):
        reserve(now=now)
    reserve(4, now=now + timedelta(days=1))
    with pytest.raises(BudgetExceeded):
        reserve(2, now=now + timedelta(days=1))
    with psycopg.connect(URL) as conn:
        assert conn.execute('select requests from quantrag.api_daily_usage order by day').fetchall() == [(5,), (4,)]
        assert conn.execute("select relrowsecurity from pg_class where oid = 'quantrag.api_daily_usage'::regclass").fetchone()[0]
