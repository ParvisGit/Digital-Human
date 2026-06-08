"""
Interim message config loader (AVA-style).
Maps tool names and intents to interim messages shown while fetching data.
Controlled by LOAD_FROM_DB environment variable.
"""
import json
import logging
import os
import random
from typing import Dict, Any, List

from Banking_agent.app.Utils.interim_repository import get_interim_messages

logger = logging.getLogger(__name__)

# Default config path relative to Banking_agent
_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "config",
    "interim_message_config.json",
)

_interim_config: Dict[str, Any] = {}
_load_source_logged: bool = False


def _should_load_from_db() -> bool:
    """Check if data should be loaded from database based on LOAD_FROM_DB env var."""
    value = os.environ.get("LOAD_FROM_DB", "false").lower().strip()
    return value in ("true", "1", "yes")


def get_interim_message_config() -> Dict[str, Any]:
    """Load and return interim message config from file (cached)."""
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
        logger.exception("[INTERIM_CONFIG] Failed to load from file: %s", e)
    return {"tool_message_mapping": {}}


def _get_interim_messages_from_file(intent_or_tool: str) -> List[str]:
    """Get interim messages from the config file."""
    config = get_interim_message_config()
    tmm = config.get("tool_message_mapping", {})
    messages = tmm.get(intent_or_tool, [])
    return messages if isinstance(messages, list) else []


def get_interim_message(intent_or_tool: str) -> str:
    """
    Get interim message for intent or tool name.
    Source controlled by LOAD_FROM_DB environment variable.
    """
    global _load_source_logged
    
    load_from_db = _should_load_from_db()
    messages = []
    source = None
    
    if load_from_db:
        # Try database first (MongoDB with Redis cache)
        messages = get_interim_messages(intent_or_tool)
        if messages:
            source = "database"
        else:
            # Fallback to file if not found in database
            messages = _get_interim_messages_from_file(intent_or_tool)
            if messages:
                source = "file (DB fallback)"
    else:
        # Load from codebase file
        messages = _get_interim_messages_from_file(intent_or_tool)
        if messages:
            source = "file"
    
    # Log source once per session to avoid log spam
    if not _load_source_logged:
        logger.info("Interim messages source: LOAD_FROM_DB=%s", load_from_db)
        _load_source_logged = True
    
    if messages:
        return random.choice(messages)
    
    logger.debug("No interim message found for %s (source=%s)", intent_or_tool, source)
    return "Please wait, I am fetching your information..."


def invalidate_interim_config():
    """Force reload of config on next access."""
    global _interim_config, _load_source_logged
    _interim_config = {}
    _load_source_logged = False
