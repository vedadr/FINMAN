"""
clarifier node
--------------
If there are pending clarification questions, this node raises interrupt()
to pause the graph. The Streamlit UI catches the interrupt, asks the user,
then resumes with the answers. On resume, we merge answers into the schema.
"""
from __future__ import annotations
from langgraph.types import interrupt
from graph.state import AgentState


def clarifier(state: AgentState) -> dict:
    pending = state.get("pending_clarifications") or []
    if not pending:
        return {}

    # Pause graph and hand control back to the Streamlit UI
    # The value passed to interrupt() is surfaced as the interrupt payload
    user_answers: dict = interrupt(
        {
            "type": "clarification",
            "questions": pending,
        }
    )
    # --- graph resumes here after Command(resume=answers) ---

    schema = dict(state.get("schema") or {})

    for item in pending:
        table = item["table"]
        col = item["column"]
        answer = user_answers.get(f"{table}.{col}", "")
        if answer and table in schema and col in schema[table]:
            schema[table][col]["description"] = answer
            schema[table][col]["ambiguous"] = False

    return {
        "schema": schema,
        "pending_clarifications": [],  # cleared after resolution
    }
