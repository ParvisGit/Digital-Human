"""LangSmith PII redaction for BFSI traces.

LangSmith stores trace inputs/outputs on its servers (cloud or self-hosted).
For banking we never want to ship full phone numbers, OTPs, account numbers,
or card numbers off-process. This module installs a global LangSmith client
configured with `hide_inputs` / `hide_outputs` callbacks that scrub those
fields before each trace event leaves the process.

Activate by calling `install_redacting_client()` ONCE at process startup
(after env vars are loaded). It's a no-op if `LANGCHAIN_TRACING_V2` /
`LANGSMITH_TRACING` is not enabled.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any

logger = logging.getLogger("banking_agent.langsmith")

# 6-digit OTPs in any field
_OTP_RE = re.compile(r"\b\d{4,8}\b")
# 10-13 digit phone-number-like sequences
_PHONE_RE = re.compile(r"\b\d{10,13}\b")
# Card numbers (13-19 digits, optionally space/dash separated)
_CARD_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")

_OTP_HINT_KEYS = {"otp", "otp_input", "otp_code", "verification_code", "code"}
_PHONE_KEYS = {"phone_number", "context_phone", "user_no", "phone"}
_REDACT_VALUE_KEYS = {"email", "email_id", "card_number", "account_number"}


def _mask_phone(value: str) -> str:
    digits = "".join(c for c in str(value) if c.isdigit())
    if len(digits) <= 4:
        return "***"
    return "x" * (len(digits) - 4) + digits[-4:]


def _mask_text(text: str) -> str:
    """Scrub OTP/phone/card patterns out of free-form text."""
    if not isinstance(text, str) or not text:
        return text
    text = _CARD_RE.sub("[REDACTED_CARD]", text)
    # Phone before OTP — phones are longer, match first
    text = _PHONE_RE.sub(lambda m: _mask_phone(m.group(0)), text)
    # OTP only when message context suggests it (avoid mangling order numbers, etc.)
    lowered = text.lower()
    if any(k in lowered for k in ("otp", "verification code", "one-time", "one time password")):
        text = _OTP_RE.sub("[REDACTED_OTP]", text)
    return text


def _redact(obj: Any) -> Any:
    """Recursively redact a payload before it leaves for LangSmith."""
    if obj is None:
        return obj
    if isinstance(obj, str):
        return _mask_text(obj)
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            key = str(k).lower()
            if key in _PHONE_KEYS and isinstance(v, str):
                out[k] = _mask_phone(v)
            elif key in _OTP_HINT_KEYS:
                out[k] = "[REDACTED_OTP]"
            elif key in _REDACT_VALUE_KEYS:
                out[k] = "[REDACTED]"
            else:
                out[k] = _redact(v)
        return out
    if isinstance(obj, (list, tuple)):
        masked = [_redact(item) for item in obj]
        return masked if isinstance(obj, list) else tuple(masked)
    return obj


def install_redacting_client() -> bool:
    """Install a global LangSmith client with PII redaction.

    Returns True if installed, False if tracing is disabled or langsmith
    isn't available.
    """
    tracing_on = (
        os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
        or os.environ.get("LANGSMITH_TRACING", "").lower() == "true"
    )
    if not tracing_on:
        logger.info("LangSmith tracing OFF — redacting client not installed")
        return False

    try:
        from langsmith import Client
        from langsmith.run_helpers import _PROJECT_NAME  # noqa: F401  (sanity import)
    except Exception as e:
        logger.warning("LangSmith SDK unavailable (%s) — redacting client not installed", e)
        return False

    api_key = os.environ.get("LANGCHAIN_API_KEY") or os.environ.get("LANGSMITH_API_KEY")
    api_url = (
        os.environ.get("LANGCHAIN_ENDPOINT")
        or os.environ.get("LANGSMITH_ENDPOINT")
        or "https://api.smith.langchain.com"
    )
    project = os.environ.get("LANGCHAIN_PROJECT") or os.environ.get("LANGSMITH_PROJECT") or "default"

    try:
        client = Client(
            api_key=api_key,
            api_url=api_url,
            hide_inputs=_redact,
            hide_outputs=_redact,
        )
    except Exception as e:
        logger.warning("Could not create redacting LangSmith client (%s) — falling back to default", e)
        return False

    # Make every LangChainTracer use this client by default.
    try:
        from langchain_core.tracers import langchain as _ltl
        _ltl._CLIENT = client  # type: ignore[attr-defined]
    except Exception:
        pass

    logger.info("LangSmith tracing ON  — project=%s endpoint=%s (PII redaction active)", project, api_url)
    return True
