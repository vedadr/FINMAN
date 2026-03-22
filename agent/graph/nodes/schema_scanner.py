"""
schema_scanner node
-------------------
Introspects all public Supabase tables, then asks GPT-4o to infer plain-English
descriptions for each column. Columns it cannot confidently describe are added
to pending_clarifications so the clarifier node can ask the user.
"""
from __future__ import annotations
import json
import os
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage

from graph.state import AgentState
from tools.supabase_client import fetch_schema_rows
from utils.schema_utils import build_schema_from_rows, is_ambiguous_column

_llm = ChatOpenAI(model="gpt-4o", temperature=0)

_SYSTEM = """You are a data analyst assistant. Given a list of database columns (name + SQL type),
infer a concise plain-English description for each column.

Respond ONLY with a valid JSON object in the following shape:
{
  "<table_name>.<column_name>": {
    "description": "<short description>",
    "confident": true or false
  },
  ...
}

Set confident=false when:
- The column name is very short or cryptic (e.g. "amt", "flg", "cd")
- The column name alone does not clearly convey its business meaning
- The type is too generic to help (e.g. just "text" or "integer" with no context)
"""


def schema_scanner(state: AgentState) -> dict:
    # Skip if schema already populated this session
    if state.get("schema"):
        return {}

    rows = fetch_schema_rows()
    if not rows:
        return {
            "schema": {},
            "pending_clarifications": [],
        }

    schema = build_schema_from_rows(rows)

    # Build prompt payload: all columns
    column_list_lines = []
    for table, cols in schema.items():
        for col, meta in cols.items():
            column_list_lines.append(f"{table}.{col} ({meta['type']})")

    column_list = "\n".join(column_list_lines)
    human_msg = HumanMessage(content=f"Infer descriptions for these columns:\n\n{column_list}")

    response = _llm.invoke([SystemMessage(content=_SYSTEM), human_msg])
    raw = response.content.strip()

    # Strip markdown fences if present
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
        if raw.endswith("```"):
            raw = raw[: raw.rfind("```")]

    try:
        inferred: dict = json.loads(raw)
    except json.JSONDecodeError:
        inferred = {}

    pending_clarifications: list[dict] = []

    for table, cols in schema.items():
        for col, meta in cols.items():
            key = f"{table}.{col}"
            info = inferred.get(key, {})
            description = info.get("description", "")
            confident = info.get("confident", True)

            schema[table][col]["description"] = description

            # Flag as ambiguous if LLM wasn't confident OR heuristic fires
            if not confident or is_ambiguous_column(col, meta["type"]):
                schema[table][col]["ambiguous"] = True
                pending_clarifications.append(
                    {
                        "table": table,
                        "column": col,
                        "type": meta["type"],
                        "inferred_description": description,
                        "question": (
                            f"What does column **`{col}`** represent in table **`{table}`**? "
                            f"(type: `{meta['type']}`"
                            + (f', currently inferred as: "{description}"' if description else "")
                            + ")"
                        ),
                    }
                )

    return {
        "schema": schema,
        "pending_clarifications": pending_clarifications,
    }
