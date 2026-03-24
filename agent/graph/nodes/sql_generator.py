"""
sql_generator node
------------------
Takes the user's plain-English query + full schema context and asks GPT-4o
to produce a safe SELECT-only SQL statement.
"""
from __future__ import annotations
import os
import re
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import AgentState
from utils.schema_utils import format_schema_for_prompt

_llm = ChatOpenAI(model="gpt-5.4-nano", temperature=0)

_BLOCKED_KEYWORDS = re.compile(
    r"\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|REPLACE|MERGE)\b",
    re.IGNORECASE,
)

_SYSTEM = """You are a SQL expert working with a PostgreSQL database (via Supabase).

Your job: translate the user's plain-English question into a single valid SELECT SQL query.

Rules:
- Output ONLY the raw SQL — no markdown, no explanation, no code fences.
- Use only SELECT statements. Never use INSERT, UPDATE, DELETE, DROP, TRUNCATE, ALTER, CREATE.
- Always qualify every table name with the schema prefix: {db_schema}.<table_name>.
- Use column names exactly as provided in the schema.
- Prefer readable column aliases (e.g. AS "Total Revenue").
- If the question is ambiguous, make a reasonable assumption and proceed.
- If an error was reported from a previous attempt, fix it.

Schema:
{schema}
"""


def sql_generator(state: AgentState) -> dict:
    schema = state.get("schema") or {}
    schema_text = format_schema_for_prompt(schema)
    user_query = state.get("user_query", "")
    error = state.get("error")

    db_schema = os.environ.get("DB_SCHEMA", "dbt_dev_marts")
    system_prompt = _SYSTEM.format(schema=schema_text, db_schema=db_schema)

    user_content = user_query
    if error:
        user_content = (
            f"{user_query}\n\n"
            f"Previous SQL attempt failed with this error:\n{error}\n"
            "Please fix the SQL."
        )

    response = _llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content),
        ]
    )

    sql = response.content.strip()
    # Strip accidental markdown fences
    if sql.startswith("```"):
        sql = "\n".join(sql.split("\n")[1:])
        if sql.strip().endswith("```"):
            sql = sql[: sql.rfind("```")].strip()

    # Safety gate
    if _BLOCKED_KEYWORDS.search(sql):
        return {
            "generated_sql": "",
            "error": "Generated SQL contained unsafe keywords and was blocked.",
        }

    return {
        "generated_sql": sql,
        "error": None,
    }
