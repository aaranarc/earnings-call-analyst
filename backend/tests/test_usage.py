from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta

import pytest
from quantrag.usage import BudgetExceeded, reserve


def test_budget_is_atomic_persistent_and_resets_per_utc_day(tmp_path, monkeypatch):
    monkeypatch.setenv("USAGE_DB_PATH", str(tmp_path / "usage.sqlite3"))
    monkeypatch.setenv("DAILY_REQUEST_LIMIT", "5")
    now = datetime(2026, 10, 15, tzinfo=UTC)

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


@pytest.mark.parametrize('units', [0, -1, True, 1.5])
def test_invalid_units_rejected(units):
    with pytest.raises(ValueError):
        reserve(units)


def test_vercel_refuses_ephemeral_budget(monkeypatch):
    from quantrag.usage import BudgetUnavailable
    monkeypatch.setenv('VERCEL', '1')
    monkeypatch.setenv('USAGE_BACKEND', 'sqlite')
    with pytest.raises(BudgetUnavailable):
        reserve()


def test_database_errors_fail_closed_and_are_redacted(monkeypatch):
    import psycopg
    from quantrag.usage import BudgetUnavailable

    monkeypatch.setenv('SUPABASE_DB_URL', 'not-a-real-secret')
    monkeypatch.setenv('USAGE_BACKEND', 'postgres')

    def broken(*args, **kwargs):
        raise psycopg.OperationalError('sensitive connection details')
    monkeypatch.setattr(psycopg, 'connect', broken)
    with pytest.raises(BudgetUnavailable) as error:
        reserve()
    assert 'sensitive' not in str(error.value)


def test_api_redacts_budget_failure(monkeypatch):
    from fastapi import HTTPException
    from quantrag import usage
    from quantrag.api import reserve_budget

    def broken(*args):
        raise usage.BudgetUnavailable('private details')
    monkeypatch.setattr(usage, 'reserve', broken)
    with pytest.raises(HTTPException) as error:
        reserve_budget()
    assert error.value.status_code == 503
    assert 'private' not in error.value.detail


def test_api_prefix_supports_public_and_binding_health(monkeypatch):
    from fastapi.testclient import TestClient
    from quantrag.api import app
    monkeypatch.setattr(app, 'root_path', '/backend')
    with TestClient(app) as client:
        assert client.get('/backend/health').status_code == 200
        assert client.get('/health').status_code == 200
        assert client.get('/backend/docs').status_code == 200
