"""
FINMAN Data Agent — Streamlit UI
=================================
Chat-style interface that drives a LangGraph agent capable of:
  • Scanning and inferring schema from Supabase tables
  • Asking the user to clarify ambiguous column meanings (inline interrupt)
  • Answering plain-English queries via text-to-SQL
  • Rendering results as interactive Plotly charts
"""
from __future__ import annotations
import os
import uuid
import json
import re

import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langgraph.types import Command
from utils.schema_annotations import save_annotations

load_dotenv()

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FINMAN Data Agent",
    page_icon="📊",
    layout="wide",
)

_VIZ_PATTERN = re.compile(
    r"\b(plot|chart|graph|visuali[sz]e|bar|line|scatter|pie|histogram|heatmap|draw)\b",
    re.IGNORECASE,
)

# ── Lazy graph compilation (once per process) ─────────────────────────────────
@st.cache_resource
def get_graph():
    from graph.graph import compile_graph
    return compile_graph()


# ── Session state bootstrap ───────────────────────────────────────────────────
def _init_session():
    defaults = {
        "thread_id": str(uuid.uuid4()),
        "messages": [],
        "schema_loaded": False,
        "schema": {},
        "awaiting_clarification": False,
        "pending_clarifications": [],
        "clarification_answers": {},
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val

_init_session()

THREAD_CONFIG = {"configurable": {"thread_id": st.session_state.thread_id}}

# ── Message helpers ───────────────────────────────────────────────────────────

def add_message(role: str, content: str, figure: str | None = None, dataframe_json: str | None = None):
    st.session_state.messages.append({
        "role": role,
        "content": content,
        "figure": figure,
        "dataframe_json": dataframe_json,
    })

# ── Graph invocation helpers ──────────────────────────────────────────────────

def _blank_state() -> dict:
    return {
        "messages": [],
        "schema": {},
        "pending_clarifications": [],
        "user_query": "",
        "generated_sql": "",
        "query_result": None,
        "viz_request": "",
        "error": None,
        "sql_retry_count": 0,
        "viz_figure": None,
    }


def _run_schema_scan():
    """First-time invocation: scan schema, interrupt if clarification needed."""
    graph = get_graph()
    try:
        for _ in graph.stream(_blank_state(), config=THREAD_CONFIG, stream_mode="values"):
            pass
    except Exception as exc:
        add_message("assistant", f"Error during schema scan: {exc}")
        return

    snapshot = graph.get_state(THREAD_CONFIG)
    sv = snapshot.values
    schema = sv.get("schema") or {}
    pending = sv.get("pending_clarifications") or []
    st.session_state.schema = schema

    if pending:
        st.session_state.pending_clarifications = pending
        st.session_state.awaiting_clarification = True
        questions_md = "\n".join(f"- {item['question']}" for item in pending)
        add_message(
            "assistant",
            f"Schema scanned successfully. I need your help clarifying a few columns "
            f"before I can answer queries accurately:\n\n{questions_md}",
        )
    else:
        st.session_state.schema_loaded = True
        save_annotations(schema)
        tables = ", ".join(f"`{t}`" for t in schema) if schema else "_none found_"
        add_message(
            "assistant",
            f"Schema loaded. Tables: {tables}.\n\nAsk me anything about your data.",
        )


def _resume_after_clarification():
    """Resume the graph after the user provided clarification answers."""
    graph = get_graph()
    answers = st.session_state.clarification_answers
    try:
        for _ in graph.stream(Command(resume=answers), config=THREAD_CONFIG, stream_mode="values"):
            pass
    except Exception as exc:
        add_message("assistant", f"Error resuming after clarification: {exc}")
        return

    snapshot = graph.get_state(THREAD_CONFIG)
    schema = snapshot.values.get("schema") or {}
    st.session_state.schema = schema
    st.session_state.schema_loaded = True
    st.session_state.awaiting_clarification = False
    st.session_state.pending_clarifications = []
    st.session_state.clarification_answers = {}

    save_annotations(schema)
    tables = ", ".join(f"`{t}`" for t in schema) if schema else "_none_"
    add_message(
        "assistant",
        f"Thank you! Column descriptions saved to `schema_annotations.md`. "
        f"Tables: {tables}.\n\nYou can now ask me questions about your data.",
    )


def _run_query(user_query: str):
    """Invoke sql_generator → data_fetcher → (visualizer) for a user query."""
    graph = get_graph()
    schema = st.session_state.schema
    viz_request = user_query if _VIZ_PATTERN.search(user_query) else ""

    # Use a fresh thread for each query so the init_router routes to sql_generator
    query_thread = {"configurable": {"thread_id": f"{st.session_state.thread_id}:q:{uuid.uuid4()}"}}

    input_state = {
        **_blank_state(),
        "schema": schema,           # schema already loaded → routes to sql_generator
        "user_query": user_query,
        "viz_request": viz_request,
        "messages": [HumanMessage(content=user_query)],
    }

    final_state: dict = {}
    try:
        for chunk in graph.stream(input_state, config=query_thread, stream_mode="values"):
            final_state = chunk
    except Exception as exc:
        add_message("assistant", f"Error running query: {exc}")
        return

    error = final_state.get("error")
    result_json: str | None = final_state.get("query_result")  # already a JSON string
    sql = final_state.get("generated_sql", "")
    viz_json = final_state.get("viz_figure")

    if error and not result_json:
        add_message("assistant", f"I encountered an error:\n```\n{error}\n```")
        return

    parts: list[str] = []
    if sql:
        parts.append(f"**Generated SQL:**\n```sql\n{sql}\n```")
    if result_json:
        import pandas as pd
        row_count = len(pd.read_json(result_json, orient="records"))
        parts.append(f"**Result:** {row_count} row(s) returned.")

    content = "\n\n".join(parts) if parts else "Query returned no results."
    add_message("assistant", content, figure=viz_json, dataframe_json=result_json)


# ── Sidebar ───────────────────────────────────────────────────────────────────

with st.sidebar:
    st.title("FINMAN Agent")
    st.markdown("---")

    supabase_url = os.environ.get("SUPABASE_URL", "")
    if supabase_url:
        short_url = supabase_url[:45] + ("..." if len(supabase_url) > 45 else "")
        st.success(f"Supabase connected\n`{short_url}`")
    else:
        st.error("SUPABASE_URL not set in .env")

    st.markdown("---")
    st.subheader("Schema")
    schema = st.session_state.get("schema", {})
    if schema:
        for table, cols in schema.items():
            with st.expander(f"**{table}** ({len(cols)} cols)"):
                for col, meta in cols.items():
                    flag = " ⚠️" if meta.get("ambiguous") else ""
                    desc = meta.get("description") or "_no description_"
                    st.markdown(f"- **{col}** `{meta['type']}`{flag}: {desc}")
    else:
        st.caption("Schema loads automatically on startup.")

    st.markdown("---")
    if st.button("Reset session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()


# ── Main chat area ────────────────────────────────────────────────────────────

st.title("📊 FINMAN Data Agent")

# Render full chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("figure"):
            fig = go.Figure(json.loads(msg["figure"]))
            st.plotly_chart(fig, use_container_width=True)
        if msg.get("dataframe_json"):
            import pandas as pd
            st.dataframe(pd.read_json(msg["dataframe_json"], orient="records"), use_container_width=True)


# ── Auto-trigger schema scan on first load ────────────────────────────────────

if (
    not st.session_state.schema_loaded
    and not st.session_state.awaiting_clarification
    and not st.session_state.messages
):
    with st.spinner("Scanning Supabase schema..."):
        _run_schema_scan()
    st.rerun()


# ── Inline clarification form ─────────────────────────────────────────────────

if st.session_state.awaiting_clarification:
    pending = st.session_state.pending_clarifications
    with st.form("clarification_form"):
        st.markdown("**Please describe the following columns to help me answer queries accurately:**")
        col_answers: dict[str, str] = {}
        for item in pending:
            key = f"{item['table']}.{item['column']}"
            col_answers[key] = st.text_input(
                label=item["question"],
                value=item.get("inferred_description", ""),
                key=f"clarify_{key}",
            )
        if st.form_submit_button("Submit"):
            st.session_state.clarification_answers = col_answers
            with st.spinner("Updating schema context..."):
                _resume_after_clarification()
            st.rerun()


# ── Chat input (active once schema is ready) ──────────────────────────────────

if st.session_state.schema_loaded:
    if user_input := st.chat_input("Ask a question about your data..."):
        add_message("user", user_input)
        with st.chat_message("user"):
            st.markdown(user_input)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                _run_query(user_input)
            last = st.session_state.messages[-1]
            st.markdown(last["content"])
            if last.get("figure"):
                fig = go.Figure(json.loads(last["figure"]))
                st.plotly_chart(fig, use_container_width=True)
            if last.get("dataframe_json"):
                import pandas as pd
                st.dataframe(pd.read_json(last["dataframe_json"], orient="records"), use_container_width=True)
