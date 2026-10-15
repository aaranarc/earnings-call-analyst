"""Atomic, restart-persistent request budget for a single API deployment."""
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


class BudgetExceeded(Exception):
    pass


def reserve(units=1, now=None):
    limit = int(os.environ.get("DAILY_REQUEST_LIMIT", "100"))
    if limit < 1:
        raise ValueError("DAILY_REQUEST_LIMIT must be positive")
    now = now or datetime.now(UTC)
    path = Path(os.environ.get("USAGE_DB_PATH", "/tmp/quantrag-usage.sqlite3"))
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path, timeout=5, isolation_level=None) as conn:
        conn.execute("create table if not exists usage (day text primary key, requests integer not null)")
        conn.execute("BEGIN IMMEDIATE")
        day = now.date().isoformat()
        row = conn.execute("select requests from usage where day=?", (day,)).fetchone()
        count = row[0] if row else 0
        if count + units > limit:
            conn.rollback()
            raise BudgetExceeded()
        conn.execute("insert into usage values (?, ?) on conflict(day) do update set requests=excluded.requests",
                     (day, count + units))
        conn.execute("delete from usage where day < ?", ((now - timedelta(days=7)).date().isoformat(),))
        conn.commit()
