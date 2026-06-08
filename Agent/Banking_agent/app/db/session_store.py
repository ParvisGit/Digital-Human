"""
Session store for greeting and authentication (AVA-style).
Stores customer_name, phone_number, greeting_done, authenticated per session.
Uses Redis when available, falls back to MongoDB (persistent across restarts).
"""
import json
import logging
from typing import Any, Optional

from Banking_agent.app.config.redis_settings import (
    get_redis_conn_string,
    is_redis_enabled,
)

logger = logging.getLogger("banking_agent.session_store")

_SESSION_TTL = 3600  # 1 hour

# MongoDB fallback collection (lazy init)
_mongo_session_collection = None
# Redis client singleton (lazy init)
_redis_client = None


def _get_mongo_collection():
    """Get MongoDB session collection (lazy init). Persistent fallback."""
    global _mongo_session_collection
    if _mongo_session_collection is None:
        from mongoengine.connection import get_db
        db = get_db()
        _mongo_session_collection = db["session_store"]
        # TTL index: auto-cleanup expired sessions
        from datetime import timedelta
        _mongo_session_collection.create_index("updated_at", expireAfterSeconds=_SESSION_TTL)
    return _mongo_session_collection


def _get_redis_client():
    """Get sync Redis client singleton. Returns None if Redis unavailable."""
    global _redis_client
    if not is_redis_enabled():
        return None
    if _redis_client is not None:
        try:
            _redis_client.ping()
            return _redis_client
        except Exception:
            _redis_client = None
    try:
        import redis
        conn = get_redis_conn_string()
        _redis_client = redis.from_url(conn, decode_responses=True)
        return _redis_client
    except Exception as e:
        logger.warning("Redis session store unavailable: %s", e)
        return None


def _key(session_id: str) -> str:
    return f"banking:session:{session_id}"


def get_session(session_id: str) -> dict[str, Any]:
    """Get session data: greeting_done, customer_name, phone_number, authenticated."""
    # Try Redis first
    client = _get_redis_client()
    if client:
        try:
            data = client.get(_key(session_id))
            if data:
                return json.loads(data)
        except Exception as e:
            logger.warning("Redis get_session failed: %s", e)

    # Fallback: MongoDB (persistent)
    try:
        coll = _get_mongo_collection()
        doc = coll.find_one({"_id": session_id})
        if doc:
            doc.pop("_id", None)
            doc.pop("updated_at", None)
            return doc
    except Exception as e:
        logger.warning("MongoDB get_session failed: %s", e)

    return {}


def set_session(session_id: str, data: dict[str, Any], ttl: int = _SESSION_TTL) -> bool:
    """Set session data. Merges with existing."""
    from datetime import datetime, timezone

    existing = get_session(session_id)
    merged = {**existing, **{k: v for k, v in data.items() if v is not None}}

    # Try Redis
    client = _get_redis_client()
    if client:
        try:
            client.setex(_key(session_id), ttl, json.dumps(merged))
            return True
        except Exception as e:
            logger.warning("Redis set_session failed: %s", e)

    # Fallback: MongoDB (persistent)
    try:
        coll = _get_mongo_collection()
        coll.update_one(
            {"_id": session_id},
            {"$set": {**merged, "updated_at": datetime.now(timezone.utc)}},
            upsert=True,
        )
        return True
    except Exception as e:
        logger.warning("MongoDB set_session failed: %s", e)

    return False


def save_greeting_done(session_id: str, customer_name: str, phone_number: str) -> bool:
    """Save that greeting was completed for this session."""
    return set_session(session_id, {
        "greeting_done": True,
        "customer_name": customer_name,
        "phone_number": sanitize_phone(phone_number),
        "conversation_state": CONV_STATE_GREETING,
    })


def save_authenticated(session_id: str, customer_name: str = "", phone_number: str = "") -> bool:
    """Save that user was authenticated, along with verified identity."""
    data = {"authenticated": True, "conversation_state": CONV_STATE_AUTHENTICATED}
    if customer_name:
        data["customer_name"] = customer_name
        data["greeting_done"] = True
    if phone_number:
        data["phone_number"] = sanitize_phone(phone_number)
    logger.info("Session %s: saving auth state %s", session_id, data)
    return set_session(session_id, data)


def save_auth_failure(session_id: str) -> int:
    """Increment and return auth failure count for this session."""
    existing = get_session(session_id)
    failures = existing.get("auth_failures", 0) + 1
    set_session(session_id, {"auth_failures": failures})
    logger.info("Session %s: auth failure count=%d", session_id, failures)
    return failures


def save_identity_verified(session_id: str, customer_name: str, phone_number: str) -> bool:
    """Save that identity (name+phone) was verified but OTP not yet done."""
    data = {"identity_verified": True, "conversation_state": CONV_STATE_OTP}
    if customer_name:
        data["customer_name"] = customer_name
        data["greeting_done"] = True
    if phone_number:
        data["phone_number"] = sanitize_phone(phone_number)
    logger.info("Session %s: identity verified (name=%s), OTP pending", session_id, customer_name)
    return set_session(session_id, data)


def save_otp_failure(session_id: str) -> int:
    """Increment and return OTP failure count for this session."""
    existing = get_session(session_id)
    failures = existing.get("otp_failures", 0) + 1
    set_session(session_id, {"otp_failures": failures})
    logger.info("Session %s: OTP failure count=%d", session_id, failures)
    return failures


# Conversation states for deterministic flow
CONV_STATE_GREETING = "GREETING"
CONV_STATE_INTENT = "INTENT"
CONV_STATE_IDENTITY = "IDENTITY"
CONV_STATE_PHONE_VERIFICATION = "PHONE_VERIFICATION"
CONV_STATE_OTP = "OTP"
CONV_STATE_AUTHENTICATED = "AUTHENTICATED"
CONV_STATE_ACTION_COMPLETE = "ACTION_COMPLETE"

# Valid state transitions
_VALID_TRANSITIONS = {
    None: [CONV_STATE_GREETING],
    CONV_STATE_GREETING: [CONV_STATE_INTENT, CONV_STATE_IDENTITY, CONV_STATE_AUTHENTICATED],
    CONV_STATE_INTENT: [CONV_STATE_IDENTITY, CONV_STATE_AUTHENTICATED],
    CONV_STATE_IDENTITY: [CONV_STATE_PHONE_VERIFICATION, CONV_STATE_OTP, CONV_STATE_AUTHENTICATED],
    CONV_STATE_PHONE_VERIFICATION: [CONV_STATE_OTP, CONV_STATE_IDENTITY],
    CONV_STATE_OTP: [CONV_STATE_AUTHENTICATED, CONV_STATE_OTP],  # OTP can retry
    CONV_STATE_AUTHENTICATED: [CONV_STATE_ACTION_COMPLETE, CONV_STATE_AUTHENTICATED],
    CONV_STATE_ACTION_COMPLETE: [CONV_STATE_INTENT],  # Can start new intent after completion
}


def get_conversation_state(session_id: str) -> Optional[str]:
    """Get current conversation state."""
    sess = get_session(session_id)
    return sess.get("conversation_state")


def set_conversation_state(session_id: str, new_state: str, force: bool = False) -> bool:
    """Set conversation state with validation. Returns True if state was set."""
    current = get_conversation_state(session_id)
    valid_next = _VALID_TRANSITIONS.get(current, [])
    
    if not force and new_state not in valid_next and current != new_state:
        logger.warning(
            "Session %s: BLOCKED state transition %s -> %s (valid: %s)",
            session_id, current, new_state, valid_next
        )
        return False
    
    set_session(session_id, {"conversation_state": new_state})
    logger.info("Session %s: state transition %s -> %s", session_id, current, new_state)
    return True


def is_state_completed(session_id: str, state: str) -> bool:
    """Check if a state has been completed (current state is later in the flow)."""
    state_order = [
        CONV_STATE_GREETING, CONV_STATE_INTENT, CONV_STATE_IDENTITY,
        CONV_STATE_PHONE_VERIFICATION, CONV_STATE_OTP, CONV_STATE_AUTHENTICATED,
        CONV_STATE_ACTION_COMPLETE
    ]
    current = get_conversation_state(session_id)
    if not current or state not in state_order:
        return False
    try:
        current_idx = state_order.index(current)
        state_idx = state_order.index(state)
        return current_idx > state_idx
    except ValueError:
        return False


def sanitize_phone(phone: str) -> str:
    """Sanitize phone number to 10 digits."""
    if not phone:
        return ""
    digits = "".join(c for c in str(phone) if c.isdigit())
    # Take last 10 digits (handles country codes)
    return digits[-10:] if len(digits) >= 10 else digits


def parse_fetch_customer_result(content: str) -> Optional[str]:
    """Parse fetch_customer_name_tool result. Returns customer_name if found."""
    try:
        data = json.loads(content) if isinstance(content, str) else content
        if isinstance(data, dict) and data.get("found") and data.get("customer_name"):
            return data["customer_name"]
    except (json.JSONDecodeError, TypeError):
        pass
    return None
