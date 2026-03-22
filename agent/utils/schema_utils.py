from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from graph.state import AgentState


def build_schema_from_rows(rows: list[dict]) -> dict[str, dict]:
    """Convert raw information_schema rows into {table: {col: {type, description, ambiguous}}}."""
    schema: dict[str, dict] = {}
    for row in rows:
        table = row["table_name"]
        col = row["column_name"]
        schema.setdefault(table, {})[col] = {
            "type": row["data_type"],
            "description": "",
            "ambiguous": False,
        }
    return schema


def format_schema_for_prompt(schema: dict[str, dict]) -> str:
    """Render the schema as a compact markdown table for LLM prompt injection."""
    lines: list[str] = []
    for table, columns in schema.items():
        lines.append(f"**Table: {table}**")
        lines.append("| Column | Type | Description |")
        lines.append("|--------|------|-------------|")
        for col, meta in columns.items():
            desc = meta.get("description") or "_unknown_"
            lines.append(f"| {col} | {meta['type']} | {desc} |")
        lines.append("")
    return "\n".join(lines)


def is_ambiguous_column(col: str, data_type: str) -> bool:
    """Heuristic: flag a column as ambiguous if it has a cryptic name or generic type."""
    generic_types = {"text", "character varying", "varchar", "integer", "numeric", "bigint", "boolean"}
    short_or_cryptic = len(col) <= 3 or col.startswith("_") or col in {"val", "amt", "num", "qty", "flg", "cd", "id"}
    return short_or_cryptic and data_type.lower() in generic_types
