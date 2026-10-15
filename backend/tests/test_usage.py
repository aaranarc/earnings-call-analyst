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
