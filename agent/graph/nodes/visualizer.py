"""
visualizer node
---------------
Given the current query_result DataFrame and the user's visualization intent,
asks GPT-4o to produce a Plotly figure. The code is executed in a sandboxed
scope and the resulting Figure is stored for Streamlit to render.
"""
from __future__ import annotations
import traceback
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

from graph.state import AgentState

_llm = ChatOpenAI(model="gpt-4o", temperature=0)

_SYSTEM = """You are a data visualization expert using Plotly in Python.

Given a pandas DataFrame called `df` and the user's chart request, write Python code
that creates a Plotly figure and assigns it to a variable called `fig`.

Rules:
- Output ONLY the raw Python code — no markdown fences, no explanation.
- You may use plotly.express (as px) or plotly.graph_objects (as go).
- The variable `df` is already defined. Do NOT redefine it.
- Always assign the final figure to `fig`.
- Use clear axis labels and a descriptive title.
- Keep the code concise.

DataFrame info:
{df_info}

Sample rows (up to 5):
{sample_rows}
"""


def visualizer(state: AgentState) -> dict:
    df: pd.DataFrame | None = state.get("query_result")
    viz_request = state.get("viz_request") or state.get("user_query", "")

    if df is None or df.empty:
        return {"error": "No data available to visualize."}

    df_info = str(df.dtypes.to_string())
    sample_rows = df.head(5).to_markdown(index=False) if hasattr(df, "to_markdown") else df.head(5).to_string(index=False)

    system_prompt = _SYSTEM.format(df_info=df_info, sample_rows=sample_rows)

    response = _llm.invoke(
        [
            SystemMessage(content=system_prompt),
            HumanMessage(content=viz_request),
        ]
    )

    code = response.content.strip()
    # Strip accidental fences
    if code.startswith("```"):
        code = "\n".join(code.split("\n")[1:])
        if code.strip().endswith("```"):
            code = code[: code.rfind("```")].strip()

    # Execute in sandboxed scope
    sandbox: dict = {
        "df": df.copy(),
        "pd": pd,
        "go": go,
        "px": px,
    }
    try:
        exec(code, sandbox)  # noqa: S102
        fig = sandbox.get("fig")
        if not isinstance(fig, go.Figure):
            return {"error": "Visualization code did not produce a valid Plotly Figure."}
        # Store as JSON-serializable dict so it survives graph state serialization
        return {"viz_figure": fig.to_json(), "error": None}
    except Exception:
        return {"error": f"Visualization error:\n{traceback.format_exc()}"}
