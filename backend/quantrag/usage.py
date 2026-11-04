"""Atomic daily request budget: SQLite locally, shared Postgres on Vercel."""
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path


class BudgetExceeded(Exception):
    pass


class BudgetUnavailable(Exception):
    """Fail closed without exposing connection details."""


def reserve_postgres(units, now, limit):
    import psycopg

    url = os.getenv("SUPABASE_DB_URL")
    if not url:
        raise BudgetUnavailable("Shared request budget is not configured")
    try:
        with psycopg.connect(url, connect_timeout=5, options="-c statement_timeout=10000") as conn:
            # Serialize the additive, idempotent migration across starting instances.
            conn.execute("select pg_advisory_xact_lock(hashtext('quantrag.api_daily_usage'))")
            conn.execute("create schema if not exists quantrag")
            conn.execute("""create table if not exists quantrag.api_daily_usage
                            (day date primary key, requests integer not null check (requests >= 0))""")
            conn.execute("alter table quantrag.api_daily_usage enable row level security")
            row = conn.execute("""
                insert into quantrag.api_daily_usage(day, requests)
                select %s::date, %s where %s <= %s
                on conflict(day) do update
                  set requests = api_daily_usage.requests + excluded.requests
                  where api_daily_usage.requests + excluded.requests <= %s
                returning requests
                """, (now.date(), units, units, limit, limit)).fetchone()
            if row is None:
                raise BudgetExceeded()
            conn.execute("delete from quantrag.api_daily_usage where day < %s",
                         ((now - timedelta(days=7)).date(),))
    except psycopg.Error as exc:
        raise BudgetUnavailable("Shared request budget is unavailable") from exc


def reserve(units=1, now=None):
    limit = int(os.environ.get("DAILY_REQUEST_LIMIT", "100"))
    if limit < 1:
        raise ValueError("DAILY_REQUEST_LIMIT must be positive")
    if not isinstance(units, int) or isinstance(units, bool) or units < 1:
        raise ValueError("Budget units must be a positive integer")
    now = now or datetime.now(UTC)
    now = now.astimezone(UTC)
    backend = os.getenv("USAGE_BACKEND", "sqlite")
    if backend == "postgres":
        return reserve_postgres(units, now, limit)
    if backend != "sqlite" or os.getenv("VERCEL") == "1":
        raise BudgetUnavailable("A shared Postgres budget is required on Vercel")
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
