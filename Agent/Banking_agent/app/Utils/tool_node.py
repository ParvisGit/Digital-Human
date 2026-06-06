"""
AVA-style tool node: execute tool calls and return ToolMessages.
Delegate tools (to_*) are not executed here - routing handles them.
"""
import json
from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode


def create_tool_node(tools: list):
    """Create a ToolNode that executes only the given tools (excludes to_* delegates)."""
    return ToolNode(tools)
