"""
Supabase client + SQL execution helpers.

Two modes for raw SQL execution:
  1. Direct Postgres connection via SUPABASE_DB_URL  (preferred)
     Format: postgresql://postgres:<password>@db.<project>.supabase.co:5432/postgres
  2. Supabase RPC fallback — requires a helper function created in your DB:

     CREATE OR REPLACE FUNCTION execute_query(query text)
     RETURNS json LANGUAGE plpgsql SECURITY DEFINER AS $$
     DECLARE result json;
     BEGIN
       EXECUTE 'SELECT json_agg(t) FROM (' || query || ') t' INTO result;
       RETURN COALESCE(result, '[]'::json);
     END;
     $$;
"""
from __future__ import annotations
import os
import functools
from typing import Any

import pandas as pd
from supabase import create_client, Client


# ── Supabase REST client ──────────────────────────────────────────────────────

@functools.lru_cache(maxsize=1)
def get_client() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ── Schema introspection ──────────────────────────────────────────────────────

def fetch_schema_rows() -> list[dict]:
    """
    Return column metadata for all public tables.
    Uses direct SQL if SUPABASE_DB_URL is set, otherwise falls back to
    the Supabase RPC execute_query function.
    """
    sql = """
        SELECT
            table_name,
            column_name,
            data_type,
            is_nullable,
            column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """
    return execute_sql(sql)


# ── SQL execution ─────────────────────────────────────────────────────────────

def execute_sql(sql: str) -> list[dict]:
    """
    Execute a SELECT query and return results as a list of dicts.

    Tries direct psycopg2 connection first (SUPABASE_DB_URL),
    then falls back to the Supabase RPC execute_query function.
    """
    db_url = os.environ.get("SUPABASE_DB_URL")
    if db_url:
        return _execute_via_psycopg2(sql, db_url)
    return _execute_via_rpc(sql)


def _execute_via_psycopg2(sql: str, db_url: str) -> list[dict]:
    try:
        import psycopg2
        import psycopg2.extras
    except ImportError as exc:
        raise RuntimeError(
            "psycopg2 is required when SUPABASE_DB_URL is set. "
            "Install it with: pip install psycopg2-binary"
        ) from exc

    conn = psycopg2.connect(db_url)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = cur.fetchall()
            return [dict(row) for row in rows]
    finally:
        conn.close()


def _execute_via_rpc(sql: str) -> list[dict]:
    """Requires the execute_query RPC function to exist in Supabase."""
    client = get_client()
    result = client.rpc("execute_query", {"query": sql}).execute()
    data = result.data
    if data is None:
        return []
    # RPC may return a JSON string or a list
    if isinstance(data, str):
        import json
        data = json.loads(data)
    return data if isinstance(data, list) else []


def execute_sql_to_df(sql: str) -> pd.DataFrame:
    """Convenience wrapper: execute SQL and return a pandas DataFrame."""
    rows = execute_sql(sql)
    return pd.DataFrame(rows)
