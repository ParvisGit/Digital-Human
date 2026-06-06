from langchain_core.tools import tool


@tool
def escalate_to_human_tool(reason: str = "customer request"):
    """Escalate the call to a human banking specialist. Use when the customer explicitly asks to speak to a human or agent, or when the AI cannot resolve the issue after trying."""
    return {
        "escalated": True,
        "reason": reason,
        "message": "Connecting you to a banking specialist. Please hold."
    }
