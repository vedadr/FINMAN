"""
LangChain tool wrappers for Plotly chart types.
These are made available to the agent as callable tools
if a tool-calling approach is preferred in future iterations.
"""
from __future__ import annotations
import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from langchain_core.tools import tool


@tool
def bar_chart(data_json: str, x: str, y: str, title: str = "Bar Chart") -> str:
    """Create a Plotly bar chart. data_json is a JSON array of row objects."""
    df = pd.DataFrame(json.loads(data_json))
    fig = px.bar(df, x=x, y=y, title=title)
    return fig.to_json()


@tool
def line_chart(data_json: str, x: str, y: str, title: str = "Line Chart") -> str:
    """Create a Plotly line chart. data_json is a JSON array of row objects."""
    df = pd.DataFrame(json.loads(data_json))
    fig = px.line(df, x=x, y=y, title=title)
    return fig.to_json()


@tool
def scatter_plot(data_json: str, x: str, y: str, color: str | None = None, title: str = "Scatter Plot") -> str:
    """Create a Plotly scatter plot. data_json is a JSON array of row objects."""
    df = pd.DataFrame(json.loads(data_json))
    fig = px.scatter(df, x=x, y=y, color=color, title=title)
    return fig.to_json()


@tool
def pie_chart(data_json: str, names: str, values: str, title: str = "Pie Chart") -> str:
    """Create a Plotly pie chart. data_json is a JSON array of row objects."""
    df = pd.DataFrame(json.loads(data_json))
    fig = px.pie(df, names=names, values=values, title=title)
    return fig.to_json()


ALL_VIZ_TOOLS = [bar_chart, line_chart, scatter_plot, pie_chart]
