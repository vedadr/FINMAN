"""
LangGraph graph assembly
------------------------
Single graph with an init_router entry node that decides whether to:
  - Run schema_scanner (first load, no schema in state)
  - Run sql_generator  (schema already loaded, user query present)
  - Stop              (schema loaded, no query yet)

Flow:
  START → init_router ──── schema_scanner → clarifier_gate → clarifier (interrupt) → END
                      └─── sql_generator → data_fetcher ─────────────────────────────────┐
                                               ↑ (retry)                                 │
                                               └─────────────── error & retry < 2 ───────┘
                                                              visualizer → END  (if viz)
                                                              END              (if table)
"""
from __future__ import annotations
import re
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from graph.state import AgentState
from graph.nodes.schema_scanner import schema_scanner
from graph.nodes.clarifier import clarifier
from graph.nodes.sql_generator import sql_generator
from graph.nodes.data_fetcher import data_fetcher
from graph.nodes.visualizer import visualizer

_VIZ_KEYWORDS = re.compile(
    r"\b(plot|chart|graph|visuali[sz]e|bar|line|scatter|pie|histogram|heatmap|draw)\b",
    re.IGNORECASE,
)

MAX_RETRIES = 2


# ── Router nodes / conditional edges ─────────────────────────────────────────

def init_router(state: AgentState) -> dict:
    """No-op node; routing logic lives in the conditional edge below."""
    return {}


def _decide_from_init(state: AgentState) -> str:
    if not state.get("schema"):
        return "schema_scanner"
    if state.get("user_query"):
        return "sql_generator"
    return END


def _decide_after_scanner(state: AgentState) -> str:
    if state.get("pending_clarifications"):
        return "clarifier"
    return END


def _decide_after_fetch(state: AgentState) -> str:
    error = state.get("error")
    retry = state.get("sql_retry_count", 0)
    if error and retry < MAX_RETRIES:
        return "sql_generator"
    if error:
        return END  # give up
    query = state.get("viz_request") or state.get("user_query", "")
    if _VIZ_KEYWORDS.search(query):
        return "visualizer"
    return END


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    builder = StateGraph(AgentState)

    builder.add_node("init_router", init_router)
    builder.add_node("schema_scanner", schema_scanner)
    builder.add_node("clarifier", clarifier)
    builder.add_node("sql_generator", sql_generator)
    builder.add_node("data_fetcher", data_fetcher)
    builder.add_node("visualizer", visualizer)

    # Entry
    builder.add_edge(START, "init_router")
    builder.add_conditional_edges(
        "init_router",
        _decide_from_init,
        {"schema_scanner": "schema_scanner", "sql_generator": "sql_generator", END: END},
    )

    # Init path
    builder.add_conditional_edges(
        "schema_scanner",
        _decide_after_scanner,
        {"clarifier": "clarifier", END: END},
    )
    builder.add_edge("clarifier", END)

    # Query path
    builder.add_edge("sql_generator", "data_fetcher")
    builder.add_conditional_edges(
        "data_fetcher",
        _decide_after_fetch,
        {"sql_generator": "sql_generator", "visualizer": "visualizer", END: END},
    )
    builder.add_edge("visualizer", END)

    return builder


def compile_graph():
    """Compile with a MemorySaver checkpointer (required for interrupt() support)."""
    builder = build_graph()
    checkpointer = MemorySaver()
    return builder.compile(checkpointer=checkpointer)
