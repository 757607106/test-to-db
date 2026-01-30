from typing import Dict, Any

from app.core.state import SQLMessageState


async def table_filter_clarification_node(state: SQLMessageState) -> Dict[str, Any]:
    connection_id = state.get("connection_id")
    if not connection_id or state.get("table_filter_confirmed", False):
        return {"current_stage": "schema_analysis"}
    return {"current_stage": "schema_analysis"}


__all__ = ["table_filter_clarification_node"]
