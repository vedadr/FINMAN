"""
data_fetcher node
-----------------
Executes the generated SQL and converts the result to a pandas DataFrame.
On failure, populates state["error"] so sql_generator can retry (up to 2 times).
"""
from __future__ import annotations
from graph.state import AgentState
from tools.supabase_client import execute_sql_to_df

MAX_RETRIES = 2


def data_fetcher(state: AgentState) -> dict:
    sql = (state.get("generated_sql") or "").strip()
    retry_count = state.get("sql_retry_count", 0)

    if not sql:
        return {
            "query_result": None,
            "error": "No SQL query was generated.",
            "sql_retry_count": retry_count + 1,
        }

    try:
        df = execute_sql_to_df(sql)
        return {
            "query_result": df,
            "error": None,
            "sql_retry_count": 0,
        }
    except Exception as exc:
        return {
            "query_result": None,
            "error": str(exc),
            "sql_retry_count": retry_count + 1,
        }
