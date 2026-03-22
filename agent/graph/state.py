from __future__ import annotations
from typing import Annotated, Any
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages


class ColumnMeta(TypedDict):
    type: str           # Postgres data type
    description: str    # LLM-inferred or user-provided
    ambiguous: bool     # True if LLM could not confidently infer context


class AgentState(TypedDict):
    messages: Annotated[list, add_messages]         # full chat history
    schema: dict[str, dict[str, ColumnMeta]]        # {table: {col: meta}}
    pending_clarifications: list[dict]              # [{table, column, type, question}]
    user_query: str                                 # latest plain-English question
    generated_sql: str                              # SQL produced by sql_generator
    query_result: Any                               # pandas DataFrame or None
    viz_request: str                                # user's visualization intent
    error: str | None                               # last execution error
    sql_retry_count: int                            # number of SQL retries so far
    viz_figure: str | None                          # Plotly figure serialized as JSON string
