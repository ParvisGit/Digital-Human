"""
Interim message config loader (AVA-style).
Maps tool names and intents to interim messages shown while fetching data.
"""
import json
import os
from typing import Dict, Any
from Banking_agent.app.Utils.interim_repository import get_interim_messages
import random

# Default config path relative to Banking_agent
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "interim_message_config.json",
)

_interim_config: Dict[str, Any] = {}


def get_interim_message_config() -> Dict[str, Any]:
    """Load and return interim message config (cached)."""
    global _interim_config
    if not _interim_config:
        _interim_config = _load_interim_config()
    return _interim_config


def _load_interim_config() -> Dict[str, Any]:
    """Load config from JSON file."""
    try:
        if os.path.exists(_CONFIG_PATH):
            with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        print(f"[INTERIM_CONFIG] Failed to load: {e}")
    return {"tool_message_mapping": {}}


# def get_interim_message(intent_or_tool: str) -> str:
#     """
#     Get interim message for intent or tool name.
#     """
#     config = get_interim_message_config()
#     tmm = config.get("tool_message_mapping", {})

#     msg = tmm.get(intent_or_tool)
#     if msg:
#         return msg

#     return "Please wait, I am fetching your information..."
def get_interim_message(intent_or_tool: str) -> str:
    messages = get_interim_messages(intent_or_tool)
    if messages:
        return random.choice(messages)
    return "Please wait, I am fetching your information..."

def invalidate_interim_config():
    """Force reload of config on next access."""
    global _interim_config
    _interim_config = {}
